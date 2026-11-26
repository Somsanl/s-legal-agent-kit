#!/usr/bin/env python3
"""UTF-8 stdio MCP entrypoint for S-Legal Workspace."""
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="strict")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
CONFIG_DIR = Path.home() / ".slegal" / "mcp"
os.environ.setdefault("SLEGAL_API_KEY_FILE", str(CONFIG_DIR / "api_key"))
os.environ.setdefault("SLEGAL_MCP_URL_FILE", str(CONFIG_DIR / "endpoint"))
sys.path.insert(0, str(HERE))

import bridge

raise SystemExit(bridge.main())
