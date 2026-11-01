#!/bin/bash
# PTVault Startup Script
# Cleanly starts PTVault with web GUI

echo "=========================================="
echo "Starting PTVault v1.0"
echo "=========================================="

# Kill any existing Flask processes
echo "1. Stopping any existing PTVault instances..."
pkill -9 -f "python.*app.py" 2>/dev/null
sleep 1

# Check if database exists, initialize if needed
if [ ! -f ./data/ptvault.db ]; then
    echo "2. Initializing database..."
    ./venv/bin/python -c "from models.database import init_db; init_db()"
else
    echo "2. Database already exists (skipping initialization)"
fi

# Start Flask
echo "3. Starting web server..."
./venv/bin/python app.py &
FLASK_PID=$!

# Wait for Flask to start
sleep 3

# Check if Flask is running
if ps -p $FLASK_PID > /dev/null; then
    echo ""
    echo "=========================================="
    echo "✓ PTVault is running!"
    echo "=========================================="
    echo ""
    echo "Open your browser to:"
    echo ""
    echo "  http://localhost:5000"
    echo ""
    echo "First time? You'll set up your master password."
    echo ""
    echo "To stop PTVault, run:"
    echo "  pkill -f 'python.*app.py'"
    echo ""
    echo "=========================================="
else
    echo ""
    echo "✗ Failed to start PTVault"
    echo "Check flask.log for errors"
    echo ""
fi
