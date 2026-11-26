#!/usr/bin/env python3
"""Automated 0%-leak public-safety scanner for S-Legal Agent Kit staging repo.

Uses structural detectors (no private names or paths embedded) and exits 0 iff
0 findings are detected across all staging files.
"""
import argparse
from pathlib import Path
import re
import sys

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".cache", "tmp"}
ALLOWED_SUFFIXES_FOR_TEXT = {
    ".py", ".ps1", ".sh", ".md", ".json", ".svg", ".txt", ".yml", ".yaml", "", ".gitignore"
}
LF_REQUIRED_EXTENSIONS = {".py", ".sh"}


def build_rules():
    return [
        ("SECRET_SLK_LITERAL", re.compile(r"\bslk_[A-Za-z0-9_\-]{12,}\b")),
        ("SECRET_PREFIX", re.compile(r"(sk_live_|sk_test_|rk_live_|pk_live_|whsec_|sbp_|sb_secret_|ghp_|gho_|github_pat_|AIza[0-9A-Za-z_-]{10,}|BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY)")),
        ("POSTGRES_CONN_STRING", re.compile(r"postgres(?:ql)?://[^:\s'\"]+:[^@\s'\"]{4,}@[^\s'\"]+")),
        ("SUPABASE_OR_VERCEL_HOST", re.compile(r"(?:vercel\.app|supabase\.(?:co|in)|pooler\.supabase\.com)", re.IGNORECASE)),
        ("PERSONAL_USER_PATH_WIN", re.compile(r"[A-Za-z]:\\Users\\[^\\\s\"'`]+", re.IGNORECASE)),
        ("PERSONAL_USER_PATH_POSIX", re.compile(r"/(?:Users|home)/[^/\s\"'`]+")),
        ("LOCAL_DRIVE_PATH", re.compile(r"\b[SD]:\\[^\s\"'`]+", re.IGNORECASE)),
        ("PRIVATE_OR_TAILSCALE_IP", re.compile(r"\b(?:100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b")),
        ("LOCALHOST_PORT", re.compile(r"(?:localhost|127\.0\.0\.1|0\.0\.0\.0):\d+")),
        ("INTERNAL_PORT", re.compile(r":(?:5432|5435|6543|15432|8000|8097|8654|8890|8927)\b")),
        ("LINE_TARGET_ID", re.compile(r"\b[UCR][0-9a-f]{32}\b")),
        ("THAI_13_DIGIT_ID", re.compile(r"(?<![0-9A-Za-z])(?!0000000000000|1234567890123|0105500000000)\d{13}(?![0-9A-Za-z])")),
        ("THAI_PHONE_NUMBER", re.compile(r"(?<!\d)(?!080-?000-?0000|081-?234-?5678|089-?000-?0000|02-?000-?0000)(?:0[689]\d[- ]?\d{3}[- ]?\d{4}|02[- ]?\d{3}[- ]?\d{4})(?!\d)")),
        ("EMAIL_ADDRESS", re.compile(r"[A-Za-z0-9._%+-]+@(?!example\.com\b|example\.org\b|example\.invalid\b)[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
        ("REAL_CASE_CODE_SL", re.compile(r"\bSL-(?:20|25)\d{2}-\d{3,}\b")),
    ]


def should_skip(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    return any(part in SKIP_DIRS for part in rel.parts)


def scan_file(path: Path, root: Path, rules):
    findings = []
    rel_str = path.relative_to(root).as_posix()
    raw = path.read_bytes()

    if raw.startswith(b"\xef\xbb\xbf") and path.suffix.lower() != ".ps1":
        findings.append((rel_str, 1, "UTF8_BOM_PRESENT", "Non-PowerShell file must not have UTF-8 BOM"))

    if path.suffix in LF_REQUIRED_EXTENSIONS and b"\r\n" in raw:
        findings.append((rel_str, 1, "CRLF_LINE_ENDING", "Python/Shell file must use LF line endings"))

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        findings.append((rel_str, 1, "NON_UTF8_FILE", str(exc)))
        return findings

    for lineno, line in enumerate(text.splitlines(), start=1):
        for rule_name, pattern in rules:
            match = pattern.search(line)
            if match:
                snippet = match.group(0)
                if len(snippet) > 40:
                    snippet = snippet[:20] + "..." + snippet[-8:]
                findings.append((rel_str, lineno, rule_name, snippet))
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description="Audit S-Legal staging repo for public safety (0% leaks).")
    parser.add_argument("target", nargs="?", default=".", help="Staging directory to audit")
    args = parser.parse_args(argv)

    root = Path(args.target).resolve()
    if not root.is_dir():
        print(f"Target directory does not exist: {root}", file=sys.stderr)
        return 2

    rules = build_rules()
    all_findings = []
    scanned_count = 0

    for item in sorted(root.rglob("*")):
        if not item.is_file() or should_skip(item, root):
            continue
        if item.name == "audit-public-safety.py":
            raw = item.read_bytes()
            rel_str = item.relative_to(root).as_posix()
            if raw.startswith(b"\xef\xbb\xbf"):
                all_findings.append((rel_str, 1, "UTF8_BOM_PRESENT", "File has UTF-8 BOM"))
            if b"\r\n" in raw:
                all_findings.append((rel_str, 1, "CRLF_LINE_ENDING", "Python file must use LF line endings"))
            scanned_count += 1
            continue
        if item.suffix.lower() not in ALLOWED_SUFFIXES_FOR_TEXT and item.name not in {"LICENSE", ".gitignore"}:
            all_findings.append((item.relative_to(root).as_posix(), 1, "UNEXPECTED_BINARY_OR_FILE", item.name))
            continue
        scanned_count += 1
        all_findings.extend(scan_file(item, root, rules))

    print(f"Audited {scanned_count} files under {root}")
    if all_findings:
        for rel_str, lineno, rule_name, detail in all_findings:
            print(f"[FAIL] {rel_str}:{lineno} [{rule_name}] {detail}")
        print(f"TOTAL FINDINGS: {len(all_findings)}")
        return 1

    print("PUBLIC SAFETY AUDIT PASSED: 0 findings (0.00% secrets/PII/personal paths)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
