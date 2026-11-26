#!/usr/bin/env bash
set -euo pipefail

# Installs or updates the S-Legal Antigravity Plugin and UTF-8 MCP Bridge on macOS/Linux.
# Supports local staging/cloned execution (--source-dir) and 1-command online install:
#   curl -fsSL https://raw.githubusercontent.com/Somsanl/s-legal-agent-kit/main/install-mac.sh | bash

REPO_ARCHIVE_URL="https://github.com/Somsanl/s-legal-agent-kit/archive/refs/heads/main.tar.gz"
SOURCE_DIR=""
TARGET_HOME="${HOME}"
BASE_URL=""
SKIP_CONFIG=0
SKIP_KEY=0
FORCE_REMOVE_COLLISION=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --source-dir)
      SOURCE_DIR="${2:-}"
      shift 2
      ;;
    --home-dir)
      TARGET_HOME="${2:-}"
      shift 2
      ;;
    --base-url)
      BASE_URL="${2:-}"
      shift 2
      ;;
    --skip-config)
      SKIP_CONFIG=1
      shift
      ;;
    --skip-key)
      SKIP_KEY=1
      shift
      ;;
    --force-remove-global-collision)
      FORCE_REMOVE_COLLISION=1
      shift
      ;;
    -h|--help)
      echo "Usage: install-mac.sh [--source-dir DIR] [--home-dir DIR] [--base-url URL] [--skip-config] [--skip-key] [--force-remove-global-collision]"
      exit 0
      ;;
    *)
      echo "[ERROR] Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

info() { printf '[S-Legal] %s\n' "$1"; }
ok()   { printf '[OK] %s\n' "$1"; }
warn() { printf '[WARN] %s\n' "$1" >&2; }

is_source_root() {
  local dir="$1"
  [ -n "$dir" ] &&
    [ -f "$dir/plugins/slegal/plugin.json" ] &&
    [ -f "$dir/mcp/bridge.py" ] &&
    [ -f "$dir/mcp/run-slegal-mcp.py" ]
}

if ! command -v python3 >/dev/null 2>&1; then
  echo "[ERROR] ไม่พบ python3 กรุณาติดตั้ง Python 3.9+ (เช่น brew install python3 หรือ xcode-select --install)" >&2
  exit 1
fi

PYTHON_BIN="$(command -v python3)"
if ! "$PYTHON_BIN" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)'; then
  echo "[ERROR] Python ต้องเป็นเวอร์ชัน 3.9 ขึ้นไป (พบ $("$PYTHON_BIN" --version 2>&1))" >&2
  exit 1
fi
PY_VER="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
ok "พบ Python $PY_VER ที่ $PYTHON_BIN"

mkdir -p "$TARGET_HOME"
TARGET_HOME="$(cd "$TARGET_HOME" && pwd)"
info "โฟลเดอร์เป้าหมายผู้ใช้: $TARGET_HOME"

TEMP_DIR=""
cleanup() {
  if [ -n "$TEMP_DIR" ] && [ -d "$TEMP_DIR" ]; then
    rm -rf "$TEMP_DIR"
  fi
}
trap cleanup EXIT

KIT_ROOT=""
SCRIPT_PATH="${BASH_SOURCE[0]:-}"
SCRIPT_DIR=""
if [ -n "$SCRIPT_PATH" ] && [ -f "$SCRIPT_PATH" ]; then
  SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
fi

if [ -n "$SOURCE_DIR" ]; then
  KIT_ROOT="$(cd "$SOURCE_DIR" && pwd)"
  if ! is_source_root "$KIT_ROOT"; then
    echo "[ERROR] --source-dir ไม่ถูกต้อง: ไม่พบ plugins/slegal/plugin.json และ mcp/bridge.py ใน $KIT_ROOT" >&2
    exit 1
  fi
elif is_source_root "$SCRIPT_DIR"; then
  KIT_ROOT="$SCRIPT_DIR"
else
  if ! command -v curl >/dev/null 2>&1; then
    echo "[ERROR] ไม่พบ curl สำหรับดาวน์โหลดชุดติดตั้งจาก GitHub" >&2
    exit 1
  fi
  TEMP_DIR="$(mktemp -d)"
  ARCHIVE_PATH="$TEMP_DIR/kit.tar.gz"
  info "กำลังดาวน์โหลด S-Legal Agent Kit จาก GitHub..."
  curl -fsSL "$REPO_ARCHIVE_URL" -o "$ARCHIVE_PATH"
  tar -xzf "$ARCHIVE_PATH" -C "$TEMP_DIR"
  for d in "$TEMP_DIR"/*; do
    if [ -d "$d" ] && is_source_root "$d"; then
      KIT_ROOT="$d"
      break
    fi
  done
  if [ -z "$KIT_ROOT" ]; then
    echo "[ERROR] แตกไฟล์จาก GitHub ไม่สำเร็จ: ไม่พบโครงสร้างปลั๊กอิน" >&2
    exit 1
  fi
fi

# 1. Install/update MCP Bridge into ~/.slegal/mcp/ (NEVER touch endpoint or api_key)
SLEGAL_DIR="$TARGET_HOME/.slegal"
MCP_DEST_DIR="$SLEGAL_DIR/mcp"
mkdir -p "$MCP_DEST_DIR"
chmod 700 "$SLEGAL_DIR" "$MCP_DEST_DIR"
cp "$KIT_ROOT/mcp/bridge.py" "$MCP_DEST_DIR/bridge.py"
cp "$KIT_ROOT/mcp/run-slegal-mcp.py" "$MCP_DEST_DIR/run-slegal-mcp.py"
chmod 600 "$MCP_DEST_DIR/bridge.py"
chmod 700 "$MCP_DEST_DIR/run-slegal-mcp.py"
RUN_SCRIPT_PATH="$MCP_DEST_DIR/run-slegal-mcp.py"
ok "ติดตั้ง MCP Bridge UTF-8 ลง $MCP_DEST_DIR เรียบร้อย"

# 2. Install/update Native Plugin into ~/.gemini/config/plugins/slegal/
GEMINI_CONFIG_DIR="$TARGET_HOME/.gemini/config"
PLUGIN_DEST_DIR="$GEMINI_CONFIG_DIR/plugins/slegal"
rm -rf "$PLUGIN_DEST_DIR"
mkdir -p "$PLUGIN_DEST_DIR"
cp -R "$KIT_ROOT/plugins/slegal/." "$PLUGIN_DEST_DIR/"

# 3. Write machine-resolved mcp_config.json inside plugin
"$PYTHON_BIN" - "$PLUGIN_DEST_DIR/mcp_config.json" "$PYTHON_BIN" "$RUN_SCRIPT_PATH" <<'PYEOF'
import json
import sys
from pathlib import Path

out_path, py_bin, run_script = sys.argv[1:4]
data = {
    "mcpServers": {
        "slegal": {
            "command": py_bin,
            "args": ["-X", "utf8", run_script],
            "env": {
                "PYTHONUTF8": "1",
                "PYTHONIOENCODING": "utf-8",
            },
        }
    }
}
Path(out_path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PYEOF
ok "ติดตั้งปลั๊กอินและตั้งค่า mcp_config.json (-X utf8) ใน $PLUGIN_DEST_DIR เรียบร้อย"

# 4. Check legacy global ~/.gemini/config/mcp_config.json collision
GLOBAL_MCP_PATH="$GEMINI_CONFIG_DIR/mcp_config.json"
if [ -f "$GLOBAL_MCP_PATH" ]; then
  if "$PYTHON_BIN" - "$GLOBAL_MCP_PATH" <<'PYEOF'
import json, sys
from pathlib import Path
try:
    obj = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    has = isinstance(obj, dict) and isinstance(obj.get("mcpServers"), dict) and ("slegal" in obj["mcpServers"])
    sys.exit(0 if has else 1)
except Exception:
    sys.exit(1)
PYEOF
  then
    STAMP="$(date +%Y%m%d-%H%M%S)"
    BACKUP_PATH="$GLOBAL_MCP_PATH.bak.$STAMP"
    cp "$GLOBAL_MCP_PATH" "$BACKUP_PATH"
    warn "พบการตั้งค่า 'slegal' เดิมซ้ำซ้อนใน $GLOBAL_MCP_PATH (สำรองไว้ที่ $BACKUP_PATH)"

    DO_REMOVE="$FORCE_REMOVE_COLLISION"
    if [ "$DO_REMOVE" -eq 0 ] && [ "$SKIP_KEY" -eq 0 ] && [ "$SKIP_CONFIG" -eq 0 ] && [ -r /dev/tty ]; then
      printf "ต้องการลบเฉพาะคีย์ 'slegal' ออกจาก Global mcp_config.json เพื่อไม่ให้ชนกับปลั๊กอินหรือไม่? (Y/n): " >/dev/tty
      read -r ans </dev/tty || ans="n"
      case "$(printf '%s' "$ans" | tr '[:upper:]' '[:lower:]')" in
        ""|y|yes) DO_REMOVE=1 ;;
      esac
    fi

    if [ "$DO_REMOVE" -eq 1 ]; then
      "$PYTHON_BIN" - "$GLOBAL_MCP_PATH" <<'PYEOF'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
obj = json.loads(p.read_text(encoding="utf-8"))
obj["mcpServers"].pop("slegal", None)
p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PYEOF
      ok "ลบคีย์ 'slegal' ที่ซ้ำซ้อนออกจาก Global mcp_config.json แล้ว (เซิร์ฟเวอร์ MCP อื่นคงเดิม 100%)"
    else
      warn "กรุณาลบ 'slegal' ออกจาก $GLOBAL_MCP_PATH ด้วยตนเองเพื่อป้องกันการโหลด MCP ซ้ำ"
    fi
  fi
fi

# 5A. S-Legal Endpoint onboarding (~/.slegal/mcp/endpoint)
ENDPOINT_FILE_PATH="$MCP_DEST_DIR/endpoint"
HAS_EXISTING_ENDPOINT=0
USED_PLACEHOLDER_ENDPOINT=0
if [ -L "$ENDPOINT_FILE_PATH" ]; then
  echo "[ERROR] ไฟล์ $ENDPOINT_FILE_PATH เป็น symlink ซึ่งไม่อนุญาต กรุณาลบและสร้างใหม่" >&2
  exit 1
fi
if [ -f "$ENDPOINT_FILE_PATH" ] && [ -s "$ENDPOINT_FILE_PATH" ]; then
  if "$PYTHON_BIN" -c 'import sys; from pathlib import Path; sys.exit(0 if Path(sys.argv[1]).read_text(encoding="utf-8-sig").strip() else 1)' "$ENDPOINT_FILE_PATH"; then
    HAS_EXISTING_ENDPOINT=1
    chmod 600 "$ENDPOINT_FILE_PATH"
    ok "พบ S-Legal Endpoint เดิมที่ $ENDPOINT_FILE_PATH — คงไว้ไม่เปลี่ยนแปลง"
  fi
fi

if [ "$HAS_EXISTING_ENDPOINT" -eq 0 ]; then
  if [ "$SKIP_CONFIG" -eq 1 ]; then
    warn "ข้ามการตั้งค่า Endpoint (--skip-config) — ก่อนใช้งานจริงให้นำ URL ใส่ใน $ENDPOINT_FILE_PATH"
  else
    RAW_ENDPOINT="$BASE_URL"
    if [ -z "$RAW_ENDPOINT" ]; then
      if [ ! -r /dev/tty ]; then
        echo "[ERROR] ไม่พบ TTY สำหรับกรอก S-Legal URL (หากรันอัตโนมัติใช้ --base-url หรือ --skip-config)" >&2
        exit 1
      fi
      printf '\n' >/dev/tty
      info "กรุณากรอก S-Legal URL ของสำนักงานท่าน (เช่น https://your-slegal-host.example.com)"
      printf "S-Legal Base URL: " >/dev/tty
      IFS= read -r RAW_ENDPOINT </dev/tty || RAW_ENDPOINT=""
    fi

    ALLOW_PH=0
    if [ "$SKIP_KEY" -eq 1 ] || [ "$SKIP_CONFIG" -eq 1 ]; then
      ALLOW_PH=1
    fi

    NORMALIZED_EP="$("$PYTHON_BIN" - "$MCP_DEST_DIR" "$ALLOW_PH" <<'PYEOF' <<<"$RAW_ENDPOINT"
import sys
sys.path.insert(0, sys.argv[1])
import bridge
allow_ph = sys.argv[2] == "1"
raw = sys.stdin.read().strip()
print(bridge.normalize_endpoint_url(raw, allow_placeholder=allow_ph))
PYEOF
)" || {
      echo "[ERROR] รูปแบบ S-Legal URL ไม่ถูกต้อง (ต้องเป็น https:// ของสำนักงานจริง)" >&2
      exit 1
    }

    (
      umask 077
      printf '%s\n' "$NORMALIZED_EP" > "$ENDPOINT_FILE_PATH"
    )
    chmod 600 "$ENDPOINT_FILE_PATH"
    ok "บันทึก S-Legal Endpoint ลง $ENDPOINT_FILE_PATH เรียบร้อย"
  fi
fi

if [ -f "$ENDPOINT_FILE_PATH" ]; then
  if "$PYTHON_BIN" -c 'import sys, urllib.parse; from pathlib import Path; h = (urllib.parse.urlsplit(Path(sys.argv[1]).read_text().strip()).hostname or "").lower(); sys.exit(0 if h == "example.com" or h.endswith(".example.com") else 1)' "$ENDPOINT_FILE_PATH"; then
    USED_PLACEHOLDER_ENDPOINT=1
  fi
fi

# 5B. Personal API Key onboarding (~/.slegal/mcp/api_key)
KEY_FILE_PATH="$MCP_DEST_DIR/api_key"
HAS_EXISTING_KEY=0
if [ -L "$KEY_FILE_PATH" ]; then
  echo "[ERROR] ไฟล์ $KEY_FILE_PATH เป็น symlink ซึ่งไม่อนุญาต กรุณาลบและสร้างใหม่" >&2
  exit 1
fi
if [ -f "$KEY_FILE_PATH" ] && [ -s "$KEY_FILE_PATH" ]; then
  if "$PYTHON_BIN" -c 'import sys; from pathlib import Path; sys.exit(0 if Path(sys.argv[1]).read_text(encoding="utf-8-sig").strip() else 1)' "$KEY_FILE_PATH"; then
    HAS_EXISTING_KEY=1
    chmod 600 "$KEY_FILE_PATH"
    ok "พบ API Key เดิมที่ $KEY_FILE_PATH — คงไว้ไม่เปลี่ยนแปลง"
  fi
fi

if [ "$HAS_EXISTING_KEY" -eq 0 ]; then
  if [ "$SKIP_KEY" -eq 1 ] || [ "$SKIP_CONFIG" -eq 1 ]; then
    warn "ข้ามการกรอก API Key (--skip-key) — ก่อนใช้งานจริงให้นำคีย์มาใส่ใน $KEY_FILE_PATH และ chmod 600"
  else
    if [ ! -r /dev/tty ]; then
      echo "[ERROR] ไม่พบ TTY สำหรับกรอก API Key แบบซ่อนตัวอักษร (หากรันอัตโนมัติใช้ --skip-key)" >&2
      exit 1
    fi
    printf '\n' >/dev/tty
    info "กรุณาวาง S-Legal API Key ของท่าน (จากเมนู ตั้งค่า > Integrations ใน S-Legal)"
    printf "S-Legal API Key (ตัวอักษรจะถูกซ่อน): " >/dev/tty
    IFS= read -r -s RAW_KEY </dev/tty || RAW_KEY=""
    printf '\n' >/dev/tty

    TRIMMED_KEY="$("$PYTHON_BIN" -c 'import re, sys; k = sys.stdin.read().strip(); ok = bool(re.fullmatch(r"slk_[0-9a-fA-F-]{36}_[A-Za-z0-9_-]{43}", k)); sys.stdout.write(k if ok else ""); sys.exit(0 if ok else 1)' <<<"$RAW_KEY")" || {
      unset RAW_KEY
      echo "[ERROR] รูปแบบ API Key ไม่ถูกต้อง (ต้องขึ้นต้นด้วย slk_ ตามมาตรฐาน S-Legal) — ไม่ได้บันทึกไฟล์" >&2
      exit 1
    }
    unset RAW_KEY

    (
      umask 077
      printf '%s\n' "$TRIMMED_KEY" > "$KEY_FILE_PATH"
    )
    unset TRIMMED_KEY
    chmod 600 "$KEY_FILE_PATH"
    ok "บันทึก API Key ลง $KEY_FILE_PATH และตั้งสิทธิ์ 600 เรียบร้อย"
  fi
fi

# 6. Post-install self-check
info "กำลังตรวจสอบการทำงานของ MCP Bridge (--check)..."
CHECK_ARGS=(-X utf8 "$RUN_SCRIPT_PATH" --check)
if { [ "$SKIP_KEY" -eq 1 ] || [ "$SKIP_CONFIG" -eq 1 ]; } && [ ! -f "$KEY_FILE_PATH" ]; then
  CHECK_ARGS+=(--allow-missing-key)
fi
if [ "$SKIP_CONFIG" -eq 1 ] && [ ! -f "$ENDPOINT_FILE_PATH" ]; then
  CHECK_ARGS+=(--allow-missing-config)
fi
if [ "$USED_PLACEHOLDER_ENDPOINT" -eq 1 ] && { [ "$SKIP_KEY" -eq 1 ] || [ "$SKIP_CONFIG" -eq 1 ]; }; then
  CHECK_ARGS+=(--allow-placeholder-endpoint)
fi
CHECK_OUT="$(SLEGAL_API_KEY_FILE="$KEY_FILE_PATH" SLEGAL_MCP_URL_FILE="$ENDPOINT_FILE_PATH" "$PYTHON_BIN" "${CHECK_ARGS[@]}")"
ok "MCP Bridge Self-Check ผ่าน: $CHECK_OUT"

if command -v agy >/dev/null 2>&1; then
  agy plugin validate "$PLUGIN_DEST_DIR" --strict --json >/dev/null
  ok "agy plugin validate --strict ผ่าน (0 errors, 0 warnings)"
fi

printf '\n'
ok "ติดตั้ง/อัปเดต S-Legal Agent Kit เสร็จสมบูรณ์!"
printf 'ขั้นตอนถัดไป: รีสตาร์ท Antigravity แล้วลองพิมพ์ "เช็กสิทธิ์ S-Legal ของฉัน"\n'
