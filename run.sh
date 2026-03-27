#!/bin/bash
# Navigate to the script directory
cd "$(dirname "$0")"

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "Error: virtual environment 'venv' not found."
    echo "Please run: python3 -m venv venv && ./venv/bin/pip install eel pillow rawpy flask exifread"
    exit 1
fi

# Run the application
echo "Starting Sorterr..."
./venv/bin/python main.py
