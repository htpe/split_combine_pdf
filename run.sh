#!/bin/bash

echo ""
echo "===================================================="
echo " PDF Split & Combine - Application Startup"
echo "===================================================="
echo ""

echo "[1/3] Checking Python installation..."
python3 --version
if [ $? -ne 0 ]; then
    echo "ERROR: Python 3 not found. Please install Python 3.8+"
    exit 1
fi

echo "[2/3] Checking dependencies..."
python3 -c "import PyQt6" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Installing dependencies..."
    python3 -m pip install -r requirements.txt
fi

echo "[3/3] Launching application..."
python3 main.py

