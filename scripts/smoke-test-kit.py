#!/usr/bin/env python3
"""Automated unit & smoke tests for S-Legal Agent Kit (stdlib-only)."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

KIT_ROOT = Path(__file__).resolve().parent.parent
MCP_DIR = KIT_ROOT / "mcp"
PLUGIN_DIR = KIT_ROOT / "plugins" / "slegal"

sys.path.insert(0, str(MCP_DIR))
import bridge  # noqa: E402


def make_synthetic_key():
    # Construct synthetically at runtime so zero key-like literals appear in source
    return "slk_" + "00000000-0000-4000-8000-000000000001" + "_" + ("A" * 43)


TEST_ENDPOINT = "https://slegal.example.invalid/api/mcp"


class FakeResponse:
    def __init__(self, url, payload, status=200):
        self._url = url
        self._body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.status = status
        self.headers = {"Content-Type": "application/json"}

    def geturl(self):
        return self._url

    def read(self, limit=-1):
        return self._body if limit < 0 else self._body[:limit]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeOpener:
    def __init__(self, handler):
        self.handler = handler
        self.calls = 0

    def open(self, req, timeout=65):
        self.calls += 1
        return self.handler(req, timeout)


class BridgeAndKitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="slegal-kit-test-"))
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))

    def test_plugin_manifests_and_skills_valid(self):
        manifest = json.loads((PLUGIN_DIR / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "slegal")
        self.assertEqual(manifest["version"], "1.0.0")
        self.assertEqual(manifest["homepage"], "https://github.com/Somsanl/s-legal-agent-kit")
        self.assertEqual(manifest["repository"], "https://github.com/Somsanl/s-legal-agent-kit")
        self.assertLessEqual(len(manifest["suggestedPrompts"]), 3)
        mcp_cfg = json.loads((PLUGIN_DIR / "mcp_config.json").read_text(encoding="utf-8"))
        self.assertIn("slegal", mcp_cfg["mcpServers"])

        expected_skills = [
            "slegal-case-intake",
            "slegal-work-tracker",
            "slegal-dbd-order",
            "thai-legal-drafting",
            "slegal-billing-ops",
            "slegal-accounting-ops",
        ]
        for skill in expected_skills:
            skill_md = PLUGIN_DIR / "skills" / skill / "SKILL.md"
            self.assertTrue(skill_md.is_file(), f"Missing {skill_md}")
            text = skill_md.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\n"), f"Missing frontmatter in {skill}")
            self.assertIn(f"name: {skill}", text)

        agents_md = PLUGIN_DIR / "rules" / "AGENTS.md"
        self.assertTrue(agents_md.is_file())
        self.assertLess(agents_md.stat().st_size, 24000)

    def test_endpoint_file_only_normalization_and_fail_closed_guards(self):
        self.assertFalse(hasattr(bridge, "ENDPOINT"), "bridge.py must not define a hardcoded default ENDPOINT")

        # Normalization: base URL -> /api/mcp
        self.assertEqual(
            bridge.normalize_endpoint_url("https://firm.example.invalid"),
            "https://firm.example.invalid/api/mcp",
        )
        self.assertEqual(
            bridge.normalize_endpoint_url("https://firm.example.invalid/api/mcp/"),
            "https://firm.example.invalid/api/mcp",
        )
        with self.assertRaises(bridge.BridgeError):
            bridge.normalize_endpoint_url("https://firm.example.invalid/login")
        with self.assertRaises(bridge.BridgeError):
            bridge.normalize_endpoint_url("https://your-slegal-host.example.com", allow_placeholder=False)

        # File-only enforcement: SLEGAL_MCP_URL env var must be ignored
        old_url_env = os.environ.get("SLEGAL_MCP_URL")
        old_url_file = os.environ.get("SLEGAL_MCP_URL_FILE")
        try:
            os.environ["SLEGAL_MCP_URL"] = TEST_ENDPOINT
            os.environ["SLEGAL_MCP_URL_FILE"] = str(self.tmp / "missing_endpoint")
            stderr_buf = io.StringIO()
            with contextlib.redirect_stderr(stderr_buf):
                with self.assertRaises(bridge.BridgeError):
                    bridge.read_endpoint_from_file()
            self.assertIn("ignored", stderr_buf.getvalue().lower())

            ep_file = self.tmp / "endpoint"
            ep_file.write_text("https://your-slegal-host.example.com\n", encoding="utf-8")
            with self.assertRaises(bridge.BridgeError):
                bridge.read_endpoint_from_file(ep_file, allow_placeholder=False)

            ep_file.write_text("https://firm.example.invalid\n", encoding="utf-8")
            self.assertEqual(bridge.read_endpoint_from_file(ep_file), "https://firm.example.invalid/api/mcp")
        finally:
            if old_url_env is None:
                os.environ.pop("SLEGAL_MCP_URL", None)
            else:
                os.environ["SLEGAL_MCP_URL"] = old_url_env
            if old_url_file is None:
                os.environ.pop("SLEGAL_MCP_URL_FILE", None)
            else:
                os.environ["SLEGAL_MCP_URL_FILE"] = old_url_file

    def test_api_key_file_only_ignores_raw_env_var(self):
        old_env_key = os.environ.get("SLEGAL_API_KEY")
        old_env_file = os.environ.get("SLEGAL_API_KEY_FILE")
        try:
            os.environ["SLEGAL_API_KEY"] = make_synthetic_key()
            os.environ["SLEGAL_API_KEY_FILE"] = str(self.tmp / "nonexistent_api_key")
            stderr_buf = io.StringIO()
            with contextlib.redirect_stderr(stderr_buf):
                with self.assertRaises(bridge.BridgeError) as ctx:
                    bridge.read_api_key_from_file()
            self.assertIn("not found", str(ctx.exception).lower())
            self.assertIn("ignored", stderr_buf.getvalue().lower())
        finally:
            if old_env_key is None:
                os.environ.pop("SLEGAL_API_KEY", None)
            else:
                os.environ["SLEGAL_API_KEY"] = old_env_key
            if old_env_file is None:
                os.environ.pop("SLEGAL_API_KEY_FILE", None)
            else:
                os.environ["SLEGAL_API_KEY_FILE"] = old_env_file

    def test_api_key_rejects_oversized_and_bad_format_without_echo(self):
        key_file = self.tmp / "api_key"
        secret_sample = make_synthetic_key()

        key_file.write_text("bad_key_content_secret_token", encoding="utf-8")
        with self.assertRaises(bridge.BridgeError) as ctx:
            bridge.read_api_key_from_file(key_file)
        self.assertNotIn("bad_key_content_secret_token", str(ctx.exception))

        key_file.write_text(secret_sample + ("x" * 520), encoding="utf-8")
        with self.assertRaises(bridge.BridgeError) as ctx:
            bridge.read_api_key_from_file(key_file)
        self.assertNotIn(secret_sample, str(ctx.exception))

        key_file.write_bytes(b"\xef\xbb\xbf" + (secret_sample + "\n").encode("utf-8"))
        self.assertEqual(bridge.read_api_key_from_file(key_file), secret_sample)

    def test_api_key_and_endpoint_reject_symlinks(self):
        target = self.tmp / "real_key"
        target.write_text(make_synthetic_key() + "\n", encoding="utf-8")
        link = self.tmp / "symlink_key"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"Symlinks require elevated/developer privilege on this host: {exc}")
        with self.assertRaises(bridge.BridgeError) as ctx:
            bridge.read_api_key_from_file(link)
        self.assertIn("symlink", str(ctx.exception).lower())

        ep_target = self.tmp / "real_ep"
        ep_target.write_text(TEST_ENDPOINT + "\n", encoding="utf-8")
        ep_link = self.tmp / "symlink_ep"
        ep_link.symlink_to(ep_target)
        with self.assertRaises(bridge.BridgeError) as ctx2:
            bridge.read_endpoint_from_file(ep_link)
        self.assertIn("symlink", str(ctx2.exception).lower())

    def test_utf8_thai_roundtrip_and_no_retry_on_timeout(self):
        key_file = self.tmp / "api_key"
        key_file.write_text(make_synthetic_key() + "\n", encoding="utf-8")
        ep_file = self.tmp / "endpoint"
        ep_file.write_text("https://slegal.example.invalid\n", encoding="utf-8")
        cache_dir = self.tmp / "cache"

        def handler(req, timeout):
            body = json.loads(req.data.decode("utf-8"))
            if body["method"] == "tools/call":
                return FakeResponse(
                    TEST_ENDPOINT,
                    {
                        "jsonrpc": "2.0",
                        "id": body["id"],
                        "result": {"content": [{"type": "text", "text": "ทดสอบภาษาไทย คดีแพ่ง ๑๒๓๔/๒๕๖๙"}]},
                    },
                )
            raise AssertionError(f"Unexpected method {body['method']}")

        opener = FakeOpener(handler)
        b = bridge.Bridge(
            bridge.read_endpoint_from_file(ep_file),
            bridge.read_api_key_from_file(key_file),
            cache_dir,
            opener=opener,
        )
        req = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "slegal_whoami", "arguments": {}}}
        raw = json.dumps(req, ensure_ascii=False).encode("utf-8")
        res = b.handle(req, raw)
        self.assertEqual(res[0]["result"]["content"][0]["text"], "ทดสอบภาษาไทย คดีแพ่ง ๑๒๓๔/๒๕๖๙")

        env = os.environ.copy()
        env["SLEGAL_API_KEY_FILE"] = str(key_file)
        env["SLEGAL_MCP_URL_FILE"] = str(ep_file)
        proc = subprocess.run(
            [sys.executable, str(MCP_DIR / "run-slegal-mcp.py"), "--check"],
            capture_output=True,
            env=env,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", errors="replace"))
        parsed = json.loads(proc.stdout.decode("utf-8"))
        self.assertTrue(parsed["ok"])
        self.assertEqual(parsed["utf8Probe"], "ทดสอบภาษาไทย-S-Legal")
        self.assertEqual(parsed["endpoint"], TEST_ENDPOINT)
        self.assertNotIn(make_synthetic_key(), proc.stdout.decode("utf-8"))

        def timeout_handler(req, timeout):
            raise TimeoutError("simulated network timeout")

        timeout_opener = FakeOpener(timeout_handler)
        b2 = bridge.Bridge(TEST_ENDPOINT, make_synthetic_key(), cache_dir, opener=timeout_opener)
        res2 = b2.handle(req, raw)
        self.assertEqual(timeout_opener.calls, 1)
        self.assertIn("error", res2[0])
        self.assertIn("check command status", res2[0]["error"]["message"].lower())

    def test_install_scripts_syntax_and_lf(self):
        ps_script = KIT_ROOT / "install-windows.ps1"
        self.assertTrue(ps_script.is_file())
        if os.name == "nt":
            ps_cmd = (
                "$errors = $null; $tokens = $null; "
                f"[void][System.Management.Automation.Language.Parser]::ParseFile('{ps_script}', [ref]$tokens, [ref]$errors); "
                "if ($errors.Count -gt 0) { $errors | ForEach-Object { Write-Error $_.Message }; exit 1 }"
            )
            res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, res.stderr + res.stdout)

        mac_script = KIT_ROOT / "install-mac.sh"
        raw = mac_script.read_bytes()
        self.assertNotIn(b"\r\n", raw, "install-mac.sh must use LF line endings")
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), "install-mac.sh must not have BOM")

        git_bash = Path(r"C:\Program Files\Git\bin\bash.exe")
        bash_bin = str(git_bash) if git_bash.is_file() else shutil.which("bash")
        if bash_bin:
            res = subprocess.run([bash_bin, "-n", str(mac_script)], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, res.stderr + res.stdout)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(BridgeAndKitTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
