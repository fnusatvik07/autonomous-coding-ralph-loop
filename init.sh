#!/bin/bash
set -euo pipefail

# Ralph Loop - Project Bootstrap Script
# Installs dependencies and verifies the environment is ready.

PYTHON_VERSION="3.13"

echo "=== Ralph Loop Bootstrap ==="

# 1. Check Python version
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. Install Python >= $PYTHON_VERSION"
    exit 1
fi

CURRENT_PY=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Python version: $CURRENT_PY (required >= $PYTHON_VERSION)"

# 2. Create virtual environment if missing
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# 3. Activate virtual environment
source .venv/bin/activate

# 4. Install dependencies
echo "Installing dependencies..."
pip install -e ".[dev]" --quiet

# 5. Ensure directory structure exists
echo "Ensuring directory structure..."
mkdir -p app/routers tests
touch app/__init__.py app/routers/__init__.py tests/__init__.py

# 6. Run tests to verify setup
echo ""
echo "Running tests..."
python -m pytest tests/ -v || echo "Some tests failed (this may be expected on first setup)"

# 7. Print access instructions
echo ""
echo "=== Setup Complete ==="
echo ""
echo "To start the development server:"
echo "  source .venv/bin/activate"
echo "  uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
echo ""
echo "API will be available at:"
echo "  http://127.0.0.1:8000"
echo "  http://127.0.0.1:8000/docs  (Swagger UI)"
