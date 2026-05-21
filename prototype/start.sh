#!/bin/bash
cd "$(dirname "$0")"

echo "======================================"
echo "  NL2SQL Prototype"
echo "======================================"
echo ""
echo "[1/2] Starting server at http://localhost:8000"
echo ""

# Open browser
if command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:8000 &
elif command -v open &> /dev/null; then
    open http://localhost:8000 &
fi

# Start server
python3 api_server.py

if [ $? -ne 0 ]; then
    echo ""
    echo "Error: Python 3 not found. Install it or run manually:"
    echo "  cd prototype"
    echo "  python3 api_server.py"
    echo ""
    read -p "Press Enter to exit..."
fi
