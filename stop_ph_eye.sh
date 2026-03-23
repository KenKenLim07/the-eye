#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./stop_ph_eye.sh [--prod] [--linux]

Options:
  --prod   Use docker-compose.prod.yml (no reload)
  --linux  Also apply docker-compose.linux.yml overrides (Linux-only features)
EOF
}

compose() {
  if command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  else
    docker compose "$@"
  fi
}

compose_file="docker-compose.yml"
include_linux_overrides=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prod) compose_file="docker-compose.prod.yml" ;;
    --linux) include_linux_overrides=true ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1"; usage; exit 2 ;;
  esac
  shift
done

files=(-f "$compose_file")
if [[ "$include_linux_overrides" == "true" && -f docker-compose.linux.yml ]]; then
  files+=(-f docker-compose.linux.yml)
fi

echo "🛑 Stopping PH Eye (Docker Compose)..."
compose "${files[@]}" down
echo "✅ Stopped"
