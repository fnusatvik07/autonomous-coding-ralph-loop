#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Todo App Setup ==="
echo ""

# Step 1: Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    echo "Virtual environment created at .venv/"
else
    echo "Virtual environment already exists at .venv/"
fi

# Step 2: Activate virtual environment
source .venv/bin/activate

# Step 3: Install dependencies
echo ""
echo "Installing dependencies..."
pip install -e '.[dev]' --quiet

# Step 4: Ensure directory structure exists
echo ""
echo "Ensuring directory structure..."
mkdir -p app/routers tests

for dir in app app/routers tests; do
    if [ ! -f "$dir/__init__.py" ]; then
        touch "$dir/__init__.py"
        echo "  Created $dir/__init__.py"
    fi
done

# Step 5: Run tests
echo ""
echo "Running tests..."
python -m pytest tests/ -v || echo "Some tests failed (this may be expected on first setup)"

# Step 6: Print usage instructions
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
echo "  http://127.0.0.1:8000/redoc (ReDoc)"
echo ""
echo "To run tests:"
echo "  source .venv/bin/activate"
echo "  python -m pytest tests/ -v"
