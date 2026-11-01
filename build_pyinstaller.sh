#!/bin/bash

# PTVault PyInstaller Build Script
# This script builds a single-file executable for PTVault

set -e

echo "=== PTVault PyInstaller Build Script ==="
echo ""

# Auto-activate virtual environment if not already active
if [ -z "$VIRTUAL_ENV" ] && [ -f "venv/bin/activate" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
elif [ -z "$VIRTUAL_ENV" ]; then
    echo "WARNING: No virtual environment active and no venv/ found."
    echo "PyInstaller must run in the same environment as your dependencies."
    echo "Run: source venv/bin/activate"
    exit 1
fi

echo "Using Python: $(which python3)"
echo ""

# Check if PyInstaller is installed (using python3 -m to ensure correct environment)
if ! python3 -m PyInstaller --version &> /dev/null; then
    echo "PyInstaller not found. Installing..."
    python3 -m pip install pyinstaller
fi

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf build dist __pycache__
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Check if .env.example exists
if [ ! -f ".env.example" ]; then
    echo "ERROR: .env.example not found!"
    exit 1
fi

# Build with PyInstaller (using python3 -m to ensure correct environment)
echo ""
echo "Building PTVault executable..."
python3 -m PyInstaller ptvault.spec --clean

# Check if build succeeded
if [ -f "dist/ptvault" ]; then
    echo ""
    echo "=== Build Successful ==="
    echo ""
    echo "Executable created at: dist/ptvault"
    echo "Size: $(du -h dist/ptvault | cut -f1)"
    echo ""
    echo "To run PTVault:"
    echo "  1. Copy dist/ptvault to your desired location"
    echo "  2. Copy .env.example to .env and configure it"
    echo "  3. Run: ./ptvault"
    echo ""
    echo "Network binding options:"
    echo "  ./ptvault                          # bind to localhost:5001 (default)"
    echo "  ./ptvault -i 0.0.0.0               # bind to all interfaces"
    echo "  ./ptvault -i 192.168.1.10          # bind to specific IP"
    echo "  ./ptvault -i 0.0.0.0 -p 8080      # custom interface and port"
    echo ""
    echo "Note: The executable needs:"
    echo "  - A .env file in the same directory (or parent)"
    echo "  - Write access to create ./data/ directory"
    echo "  - SQLCipher library installed on the system"
    echo ""
else
    echo ""
    echo "=== Build Failed ==="
    echo "Check the error messages above for details."
    exit 1
fi
