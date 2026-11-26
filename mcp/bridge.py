#!/usr/bin/env python3
"""Portable UTF-8 stdio bridge for S-Legal's API-key authenticated HTTP MCP endpoint.

Only initialize/tools-list metadata is cached. Business requests are forwarded
once, with their original JSON bytes; a timeout never retries a financial write.
Python 3.9+, standard library only. Endpoint URL and API key are read strictly
from local files (~/.slegal/mcp/endpoint and ~/.slegal/mcp/api_key).
"""
import argparse
import base64
import contextlib
import email.utils
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

TTL = 300
MAX_INPUT = 15 * 1024 * 1024
MAX_RESPONSE = 2 * 1024 * 1024
MAX_CONFIG_FILE_BYTES = 512
KEY_PATTERN = re.compile(r"slk_[0-9a-fA-F-]{36}_[A-Za-z0-9_-]{43}\Z")
PROTOCOL_PATTERN = re.compile(r"20\d{2}-\d{2}-\d{2}\Z")


class BridgeError(Exception):
    def __init__(self, message, code=-32000, retry_after=None):
        super().__init__(message)
        self.code, self.retry_after = code, retry_after


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def default_key_file():
    return Path.home() / ".slegal" / "mcp" / "api_key"


def default_endpoint_file():
    return Path.home() / ".slegal" / "mcp" / "endpoint"


def configure_utf8_streams():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="strict")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def write_json_line(payload):
    raw = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    if hasattr(sys.stdout, "buffer"):
        sys.stdout.buffer.write(raw)
        sys.stdout.buffer.flush()
    else:
        sys.stdout.write(raw.decode("utf-8"))
        sys.stdout.flush()


def private_directory(directory):
    directory = Path(directory).expanduser()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if directory.is_symlink() or not directory.is_dir():
        raise BridgeError("Private metadata cache is unavailable")
    if os.name != "nt" and directory.stat().st_uid != os.getuid():
        raise BridgeError("Private metadata cache is unavailable")
    if os.name != "nt":
        directory.chmod(0o700)
    return directory


def open_private(path):
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(str(path), flags, 0o600)
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise BridgeError("Private metadata cache is unavailable")
    if os.name != "nt" and os.fstat(fd).st_uid != os.getuid():
        os.close(fd)
        raise BridgeError("Private metadata cache is unavailable")
    if os.name != "nt":
        os.fchmod(fd, 0o600) if hasattr(os, "fchmod") else os.chmod(path, 0o600)
    return os.fdopen(fd, "r+b")


@contextlib.contextmanager
def file_lock(path, wait_seconds=5):
    with open_private(path) as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        deadline = time.monotonic() + wait_seconds
        while True:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (BlockingIOError, OSError):
                if time.monotonic() >= deadline:
                    raise BridgeError("Metadata refresh is busy; try again shortly", -32001, 1)
                time.sleep(0.025)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def load_json(path):
    try:
        if path.is_symlink() or path.stat().st_size > MAX_RESPONSE:
            return {}
        with open_private(path) as handle:
            value = json.loads(handle.read(MAX_RESPONSE + 1).decode("utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, UnicodeError):
        return {}


def save_json(path, value):
    fd, temporary = tempfile.mkstemp(prefix=".metadata-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            if os.name != "nt":
                os.chmod(temporary, 0o600)
            handle.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def rpc_error(request_id, error):
    detail = {"code": error.code, "message": str(error)}
    if error.retry_after is not None:
        detail["data"] = {"retryAfterSeconds": error.retry_after}
    return {"jsonrpc": "2.0", "id": request_id, "error": detail}


def decode_messages(raw, content_type):
    try:
        text = raw.decode("utf-8")
        if "text/event-stream" in content_type.lower():
            messages = []
            for event in text.replace("\r\n", "\n").split("\n\n"):
                payload = "\n".join(line[5:].lstrip() for line in event.split("\n") if line.startswith("data:"))
                if payload:
                    messages.append(json.loads(payload))
        elif not raw:
            return []
        else:
            messages = [json.loads(text)]
        if not all(isinstance(message, dict) and message.get("jsonrpc") == "2.0" for message in messages):
            raise ValueError()
        return messages
    except (ValueError, UnicodeError):
        raise BridgeError("S-Legal returned an unexpected MCP response; no request was retried")


def retry_delay(headers, raw):
    value = headers.get("Retry-After", "")
    seconds = None
    try:
        seconds = float(value)
    except (ValueError, TypeError):
        try:
            seconds = email.utils.parsedate_to_datetime(value).timestamp() - time.time()
        except (ValueError, TypeError, AttributeError, OverflowError):
            pass
    if seconds is None:
        try:
            payload = json.loads(raw.decode("utf-8"))
            error = payload.get("error", {})
            seconds = float(error.get("retryAfterSeconds", error.get("data", {}).get("retryAfterSeconds", 60)))
        except (ValueError, TypeError, AttributeError, UnicodeError):
            seconds = 60
    if not math.isfinite(seconds):
        seconds = 60
    return max(60, min(3600, math.ceil(seconds)))


def _read_regular_utf8_file(path: Path, label: str, enforce_private_mode: bool = False) -> str:
    if path.is_symlink():
        raise BridgeError(f"{label} must not be a symlink")
    if not path.exists():
        raise BridgeError(f"{label} not found")

    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(str(path), flags)
    except OSError as exc:
        raise BridgeError(f"Unable to open {label} safely") from exc

    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise BridgeError(f"{label} path must be a regular file")
        if os.name != "nt":
            if st.st_uid != os.getuid():
                raise BridgeError(f"{label} owner mismatch")
            if enforce_private_mode and (st.st_mode & 0o077 != 0):
                print(
                    f"Warning: {label} permissions are too open; run: chmod 600 ~/.slegal/mcp/api_key",
                    file=sys.stderr,
                )
        if st.st_size > MAX_CONFIG_FILE_BYTES:
            raise BridgeError(f"{label} is invalid (exceeds {MAX_CONFIG_FILE_BYTES} bytes)")
        with os.fdopen(fd, "rb") as handle:
            fd = -1
            raw = handle.read(MAX_CONFIG_FILE_BYTES + 1)
    finally:
        if fd != -1:
            os.close(fd)

    if len(raw) > MAX_CONFIG_FILE_BYTES:
        raise BridgeError(f"{label} is invalid (exceeds {MAX_CONFIG_FILE_BYTES} bytes)")

    try:
        return raw.decode("utf-8-sig").strip()
    except UnicodeError as exc:
        raise BridgeError(f"{label} must be valid UTF-8 text") from exc


def normalize_endpoint_url(raw_url: str, allow_placeholder: bool = False) -> str:
    raw_url = (raw_url or "").strip()
    if not raw_url:
        raise BridgeError("S-Legal endpoint file (~/.slegal/mcp/endpoint) is empty")
    parsed = urllib.parse.urlsplit(raw_url)
    host = (parsed.hostname or "").lower()
    if (
        parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or not host
        or (
            parsed.scheme != "https"
            and not (parsed.scheme == "http" and host in {"localhost", "127.0.0.1", "::1"})
        )
    ):
        raise BridgeError("S-Legal endpoint configuration is invalid")

    if not allow_placeholder and (host == "example.com" or host.endswith(".example.com")):
        raise BridgeError("S-Legal endpoint is still set to placeholder example.com; configure your real host in ~/.slegal/mcp/endpoint")

    clean_path = parsed.path.rstrip("/")
    if clean_path in ("",):
        norm_path = "/api/mcp"
    elif clean_path == "/api/mcp":
        norm_path = "/api/mcp"
    else:
        raise BridgeError("S-Legal endpoint path must be the base URL or end with /api/mcp")

    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, norm_path, "", ""))


def read_endpoint_from_file(endpoint_file_path=None, allow_placeholder: bool = False) -> str:
    """Read and normalize the S-Legal MCP endpoint strictly from ~/.slegal/mcp/endpoint."""
    if os.getenv("SLEGAL_MCP_URL"):
        print(
            "Warning: SLEGAL_MCP_URL env var is ignored; reading endpoint strictly from ~/.slegal/mcp/endpoint.",
            file=sys.stderr,
        )

    raw_path = endpoint_file_path or os.getenv("SLEGAL_MCP_URL_FILE") or str(default_endpoint_file())
    path = Path(raw_path).expanduser()
    text = _read_regular_utf8_file(path, "S-Legal endpoint file (~/.slegal/mcp/endpoint)")
    return normalize_endpoint_url(text, allow_placeholder=allow_placeholder)


def read_api_key_from_file(key_file_path=None) -> str:
    """Read and validate the S-Legal API key strictly from ~/.slegal/mcp/api_key."""
    if os.getenv("SLEGAL_API_KEY"):
        print(
            "Warning: SLEGAL_API_KEY env var is ignored; reading API key strictly from ~/.slegal/mcp/api_key.",
            file=sys.stderr,
        )

    raw_path = key_file_path or os.getenv("SLEGAL_API_KEY_FILE") or str(default_key_file())
    path = Path(raw_path).expanduser()
    key = _read_regular_utf8_file(path, "S-Legal API key file (~/.slegal/mcp/api_key)", enforce_private_mode=True)
    if not KEY_PATTERN.fullmatch(key):
        raise BridgeError("S-Legal API key format in ~/.slegal/mcp/api_key is invalid")
    return key


class Bridge:
    def __init__(self, endpoint, key, cache_directory, opener=None):
        self.endpoint = normalize_endpoint_url(endpoint, allow_placeholder=False)
        if not KEY_PATTERN.fullmatch(key):
            raise BridgeError("S-Legal API key configuration is invalid")
        self.key = key
        self.directory = private_directory(cache_directory)
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        self.identity = hashlib.sha256((self.endpoint + "\0" + digest).encode("utf-8")).hexdigest()
        self.control_path = self.directory / (self.identity + ".control.json")
        self.control_lock = self.directory / (self.identity + ".control.lock")
        self.opener = opener or urllib.request.build_opener(NoRedirect())
        self.protocol = "2025-03-26"
        self.cache_protocol = self.protocol
        self.initialized = False

    def metadata_path(self, protocol):
        digest = hashlib.sha256((self.identity + "\0" + protocol).encode("utf-8")).hexdigest()
        return self.directory / (digest + ".metadata.json")

    def control(self):
        with file_lock(self.control_lock):
            return load_json(self.control_path)

    def cooldown(self):
        remaining = self.control().get("cooldown_until", 0) - time.time()
        if remaining > 0:
            raise BridgeError("S-Legal rate limit cooldown; no remote request was sent", -32029, max(1, math.ceil(remaining)))

    def remote(self, message, raw):
        self.cooldown()
        headers = {
            "Authorization": "Bearer " + self.key,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": self.protocol,
            "User-Agent": "slegal-private-stdio-bridge/1.3",
        }
        request = urllib.request.Request(self.endpoint, data=raw, headers=headers, method="POST")
        try:
            with self.opener.open(request, timeout=65) as response:
                if response.geturl() != self.endpoint:
                    raise BridgeError("S-Legal redirected the connection; no request was retried")
                body = response.read(MAX_RESPONSE + 1)
                if len(body) > MAX_RESPONSE:
                    raise BridgeError("S-Legal response exceeded the limit; no request was retried")
                messages = decode_messages(body, response.headers.get("Content-Type", ""))
        except urllib.error.HTTPError as error:
            try:
                body = error.read(MAX_RESPONSE + 1)
                status, error_headers = error.code, error.headers
            finally:
                error.close()
            if status == 429:
                delay = retry_delay(error_headers, body)
                with file_lock(self.control_lock):
                    control = load_json(self.control_path)
                    control["cooldown_until"] = max(control.get("cooldown_until", 0), time.time() + delay)
                    save_json(self.control_path, control)
                raise BridgeError("S-Legal rate limit cooldown; no request was retried", -32029, delay)
            if status in {401, 403}:
                self.initialized = False
                with file_lock(self.control_lock):
                    control = load_json(self.control_path)
                    control["invalidated_at"] = time.time()
                    control["cooldown_until"] = max(control.get("cooldown_until", 0), time.time() + 60)
                    save_json(self.control_path, control)
                raise BridgeError("S-Legal rejected this request (HTTP %s); reconnect cooldown is active" % status, retry_after=60)
            raise BridgeError("S-Legal rejected this request (HTTP %s); no request was retried" % status)
        except (urllib.error.URLError, TimeoutError, OSError):
            raise BridgeError("Connection outcome is unknown; check command status before retrying a write")
        if "id" in message and not any(item.get("id") == message["id"] and ("result" in item or "error" in item) for item in messages):
            raise BridgeError("S-Legal returned no matching MCP response; no request was retried")
        return messages

    def cached_metadata(self, path):
        cache = load_json(path)
        control = self.control()
        created = cache.get("created_at", 0)
        expires = cache.get("expires_at", 0)
        if (
            not isinstance(created, (int, float))
            or not isinstance(expires, (int, float))
            or not created <= time.time() < expires <= created + TTL
            or created <= control.get("invalidated_at", 0)
        ):
            return {}
        return cache

    def metadata(self, message, raw):
        method = message["method"]
        if method == "initialize":
            params = message.get("params") or {}
            protocol = params.get("protocolVersion") if isinstance(params, dict) else None
            if not isinstance(protocol, str) or not PROTOCOL_PATTERN.fullmatch(protocol):
                raise BridgeError("Initialize requires a valid protocolVersion", -32602)
            self.cache_protocol = protocol
            self.protocol = protocol
        path = self.metadata_path(self.cache_protocol)
        with file_lock(path.with_suffix(".lock")):
            cache = self.cached_metadata(path)
            field = "initialize" if method == "initialize" else "tools"
            saved = cache.get(field)
            if isinstance(saved, dict):
                if method == "initialize":
                    self.protocol = saved["protocolVersion"]
                    self.initialized = True
                return [{"jsonrpc": "2.0", "id": message["id"], "result": saved}]
            messages = self.remote(message, raw)
            response = next((item for item in messages if item.get("id") == message["id"]), {})
            result = response.get("result")
            if isinstance(result, dict):
                if method == "initialize":
                    version = result.get("protocolVersion")
                    if (
                        isinstance(version, str)
                        and PROTOCOL_PATTERN.fullmatch(version)
                        and result.get("serverInfo", {}).get("name") == "slegal-accounting"
                    ):
                        now = time.time()
                        cache = {"created_at": now, "expires_at": now + TTL, "initialize": result}
                        self.protocol, self.initialized = version, True
                        save_json(path, cache)
                elif isinstance(result.get("tools"), list):
                    if not cache:
                        now = time.time()
                        cache = {"created_at": now, "expires_at": now + TTL}
                    cache["tools"] = result
                    save_json(path, cache)
            return messages

    def handle(self, message, raw):
        request_id = message.get("id") if isinstance(message, dict) else None
        try:
            if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
                raise BridgeError("Invalid JSON-RPC request", -32600)
            method = message["method"]
            if method == "server/discover":
                raise BridgeError("Use the legacy initialize handshake with this bridge", -32601)
            if method == "notifications/roots/list_changed":
                return []
            if self.initialized and method == "notifications/initialized":
                return []
            if self.initialized and method == "ping" and "id" in message:
                return [{"jsonrpc": "2.0", "id": request_id, "result": {}}]
            if "id" in message and (
                method == "initialize"
                or (method == "tools/list" and self.initialized and message.get("params") in (None, {}))
            ):
                return self.metadata(message, raw)
            if method == "tools/call":
                params = message.get("params")
                args = params.get("arguments") if isinstance(params, dict) else None
                pdf_path_raw = args.get("pdfFilePath") if isinstance(args, dict) else None
                if isinstance(pdf_path_raw, str) and pdf_path_raw.strip() and not args.get("pdfBase64"):
                    pdf_path = Path(pdf_path_raw.strip()).expanduser()
                    if pdf_path.is_file() and not pdf_path.is_symlink() and pdf_path.stat().st_size <= 8 * 1024 * 1024:
                        args["pdfBase64"] = base64.b64encode(pdf_path.read_bytes()).decode("ascii")
                        args.setdefault("pdfFileName", pdf_path.name)
                        del args["pdfFilePath"]
                        raw = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            return self.remote(message, raw)
        except BridgeError as error:
            return [rpc_error(request_id, error)] if isinstance(message, dict) and "id" in message else []


def default_cache_dir():
    cache_base = os.getenv("LOCALAPPDATA") if os.name == "nt" else os.getenv("XDG_CACHE_HOME")
    default_cache = Path(cache_base).expanduser() if cache_base else Path.home() / ".cache"
    return os.getenv("SLEGAL_MCP_CACHE_DIR") or (default_cache / "slegal-mcp")


def configured_bridge():
    endpoint = read_endpoint_from_file(allow_placeholder=False)
    key = read_api_key_from_file()
    return Bridge(endpoint, key, default_cache_dir())


def run_self_check(allow_missing_key=False, allow_missing_config=False, allow_placeholder_endpoint=False):
    configure_utf8_streams()

    endpoint_status = "valid"
    endpoint_value = None
    try:
        endpoint_value = read_endpoint_from_file(allow_placeholder=False)
    except BridgeError as exc:
        ep_path = Path(os.getenv("SLEGAL_MCP_URL_FILE") or str(default_endpoint_file())).expanduser()
        if allow_missing_config and not ep_path.exists() and not ep_path.is_symlink():
            endpoint_status = "missing_skipped"
        elif allow_placeholder_endpoint and ep_path.exists() and not ep_path.is_symlink():
            try:
                endpoint_value = read_endpoint_from_file(allow_placeholder=True)
                endpoint_status = "placeholder_dry_run"
            except BridgeError as inner_exc:
                write_json_line({"ok": False, "endpointStatus": "invalid", "error": str(inner_exc)})
                return 2
        else:
            write_json_line({"ok": False, "endpointStatus": "invalid", "error": str(exc)})
            return 2

    key_status = "valid"
    try:
        read_api_key_from_file()
    except BridgeError as exc:
        key_path = Path(os.getenv("SLEGAL_API_KEY_FILE") or str(default_key_file())).expanduser()
        if (allow_missing_key or allow_missing_config) and not key_path.exists() and not key_path.is_symlink():
            key_status = "missing_skipped"
        else:
            write_json_line({"ok": False, "keyStatus": "invalid", "error": str(exc)})
            return 2

    write_json_line(
        {
            "ok": True,
            "python": sys.version.split()[0],
            "utf8Probe": "ทดสอบภาษาไทย-S-Legal",
            "endpointStatus": endpoint_status,
            "keyStatus": key_status,
            "endpoint": endpoint_value,
        }
    )
    return 0


def main(argv=None):
    configure_utf8_streams()
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--check", action="store_true", help="Run local UTF-8, endpoint, and API key file self-check without network calls")
    parser.add_argument("--allow-missing-key", action="store_true", help="Allow missing api_key during --check dry-run")
    parser.add_argument("--allow-missing-config", action="store_true", help="Allow missing endpoint and api_key during --check dry-run")
    parser.add_argument("--allow-placeholder-endpoint", action="store_true", help="Allow example.com endpoint during --check sandbox dry-run")
    args, unknown = parser.parse_known_args(argv)
    if unknown:
        print("Unsupported arguments.", file=sys.stderr)
        return 2
    if args.check:
        return run_self_check(
            allow_missing_key=args.allow_missing_key,
            allow_missing_config=args.allow_missing_config,
            allow_placeholder_endpoint=args.allow_placeholder_endpoint,
        )

    try:
        bridge = configured_bridge()
    except (BridgeError, OSError, UnicodeError) as exc:
        print(f"S-Legal bridge configuration is unavailable: {exc}", file=sys.stderr)
        return 2

    while True:
        line = sys.stdin.buffer.readline(MAX_INPUT + 1)
        if not line:
            return 0
        if len(line) > MAX_INPUT:
            while line and not line.endswith(b"\n"):
                line = sys.stdin.buffer.readline(MAX_INPUT + 1)
            messages = [rpc_error(None, BridgeError("MCP request exceeds the size limit", -32600))]
        else:
            try:
                message = json.loads(line.decode("utf-8"))
                if not isinstance(message, dict):
                    raise ValueError()
                messages = bridge.handle(message, line)
            except (ValueError, UnicodeError):
                messages = [rpc_error(None, BridgeError("Invalid JSON-RPC input", -32700))]
            except Exception:
                messages = [rpc_error(None, BridgeError("Bridge request failed safely; no request was retried"))]
        for message in messages:
            write_json_line(message)


if __name__ == "__main__":
    sys.exit(main())
