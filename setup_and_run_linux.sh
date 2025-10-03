#!/bin/bash

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# List of required packages
packages=(pandas matplotlib numpy)

# Install missing packages only
for pkg in "${packages[@]}"
do
    if ! pip show "$pkg" > /dev/null 2>&1; then
        echo "Installing $pkg..."
        pip install "$pkg"
    else
        echo "$pkg already installed."
    fi
done

# Run your Python script within the activated environment
python3 main.py

