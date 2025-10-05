#!/bin/bash

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip to the latest version
pip install --upgrade pip

# Install all packages listed in requirements.txt
pip install -r requirements.txt


