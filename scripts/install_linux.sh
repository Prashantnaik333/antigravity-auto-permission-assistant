#!/usr/bin/env bash
# Antigravity Auto Permission Assistant (AAPA) - Linux/macOS Installer
set -e

echo "=========================================================="
echo "  Antigravity Auto Permission Assistant (AAPA) Installer  "
echo "=========================================================="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$REPO_ROOT"

# Check Python 3
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 could not be found. Please install Python 3.11+."
    exit 1
fi

echo "[1/4] Setting up virtual environment (.venv)..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

echo "[2/4] Installing dependencies..."
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install -e .

echo "[3/4] Running verification self-tests..."
.venv/bin/python -m pytest tests -q

echo "[4/4] Creating executable runner..."
cat << 'EOF' > run_linux.sh
#!/usr/bin/env bash
cd "$(dirname "$0")"
.venv/bin/python -m aapa.main "$@"
EOF
chmod +x run_linux.sh

echo ""
echo "Installation complete! Launch AAPA with:"
echo "  ./run_linux.sh"
echo ""
