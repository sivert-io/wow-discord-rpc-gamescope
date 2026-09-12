#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VENV="${CRAFTPRESENCE_VENV:-$HOME/.local/share/craftpresence-gamescope-venv}"
PYTHON_BIN="${PYTHON:-python3}"
AUTOSTART=0
WOW_DIR=""

usage() {
  cat <<'EOF'
Usage: ./install.sh [WOW_DIR] [--autostart]

Examples:
  ./install.sh "$HOME/Games/WoW-3.3.5a"
  ./install.sh "$HOME/Games/WoW-3.3.5a" --autostart

If WOW_DIR is omitted, the installer tries to find exactly one Wow.exe under ~/Games.
EOF
}

for arg in "$@"; do
  case "$arg" in
    --autostart)
      AUTOSTART=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --*)
      echo "Unknown option: $arg" >&2
      usage >&2
      exit 2
      ;;
    *)
      if [[ -n "$WOW_DIR" ]]; then
        echo "Only one WOW_DIR may be supplied." >&2
        exit 2
      fi
      WOW_DIR="$arg"
      ;;
  esac
done

if [[ -z "$WOW_DIR" ]]; then
  mapfile -d '' candidates < <(find "$HOME/Games" -maxdepth 5 -type f -iname 'Wow.exe' -print0 2>/dev/null || true)
  if [[ ${#candidates[@]} -eq 1 ]]; then
    WOW_DIR="$(dirname -- "${candidates[0]}")"
    echo "Detected WoW directory: $WOW_DIR"
  elif [[ ${#candidates[@]} -eq 0 ]]; then
    echo "Could not find Wow.exe under $HOME/Games." >&2
    usage >&2
    exit 1
  else
    echo "Found multiple Wow.exe files. Pass the intended WoW directory explicitly:" >&2
    for exe in "${candidates[@]}"; do
      printf '  %s\n' "$(dirname -- "$exe")" >&2
    done
    exit 1
  fi
fi

WOW_DIR="$(cd -- "$WOW_DIR" && pwd)"
SCRIPT_DIR="$WOW_DIR/Interface/AddOns/CraftPresence/Script"
UPSTREAM="$SCRIPT_DIR/DiscordRichPresence.py"
HELPER="$SCRIPT_DIR/DiscordRichPresenceGamescope.py"
CONFIG="$SCRIPT_DIR/config.json"

if [[ ! -f "$WOW_DIR/Wow.exe" ]]; then
  echo "Wow.exe not found in: $WOW_DIR" >&2
  exit 1
fi

if [[ ! -f "$UPSTREAM" ]]; then
  echo "CraftPresence upstream helper not found:" >&2
  echo "  $UPSTREAM" >&2
  echo "Install CraftPresence first, then rerun this installer." >&2
  exit 1
fi

command -v "$PYTHON_BIN" >/dev/null 2>&1 || {
  echo "Python executable not found: $PYTHON_BIN" >&2
  exit 1
}

echo "Creating/updating virtual environment: $VENV"
"$PYTHON_BIN" -m venv "$VENV"
"$VENV/bin/python" -m pip install --upgrade pip
"$VENV/bin/python" -m pip install -r "$REPO_DIR/requirements.txt"

echo "Installing helper into CraftPresence..."
install -m 0755 "$REPO_DIR/DiscordRichPresenceGamescope.py" "$HELPER"

if [[ ! -f "$CONFIG" ]]; then
  install -m 0644 "$REPO_DIR/config.example.json" "$CONFIG"
  echo "Created $CONFIG"
else
  echo "Keeping existing $CONFIG"
fi

if [[ "$AUTOSTART" -eq 1 ]]; then
  UNIT_DIR="$HOME/.config/systemd/user"
  UNIT_PATH="$UNIT_DIR/wow-discord-rpc-gamescope.service"
  mkdir -p "$UNIT_DIR"

  cat > "$UNIT_PATH" <<EOF
[Unit]
Description=WoW Discord Rich Presence via Gamescope
After=graphical-session.target

[Service]
Type=simple
ExecStart="$VENV/bin/python" "$HELPER"
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
EOF

  systemctl --user daemon-reload
  systemctl --user enable --now wow-discord-rpc-gamescope.service
  echo
  echo "Background service enabled and started."
  echo "Logs: journalctl --user -u wow-discord-rpc-gamescope -f"
else
  echo
  echo "Installed. Run manually with:"
  printf '  %q %q\n' "$VENV/bin/python" "$HELPER"
  echo
  echo "To enable background autostart later, rerun with --autostart."
fi

cat <<EOF

Done.
WoW:     $WOW_DIR
Helper:  $HELPER
Venv:    $VENV
EOF
