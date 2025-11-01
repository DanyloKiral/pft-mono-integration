#!/bin/bash

# Firefly Integration Runner
# This script sets up the environment and runs the Monobank->Firefly integration

set -e  # Exit on error

echo "$(date) - Starting Monobank->Firefly integration setup"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Configuration
CONFIG_FILE="${1:-config.json}"
CREDENTIALS_FILE="${2:-credentials.json}"
VENV_DIR="venv"

echo "Using config: $CONFIG_FILE"
echo "Using credentials: $CREDENTIALS_FILE"

# Check if config files exist
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Config file '$CONFIG_FILE' not found"
    exit 1
fi

if [ ! -f "$CREDENTIALS_FILE" ]; then
    echo "Error: Credentials file '$CREDENTIALS_FILE' not found"
    exit 1
fi

# Create logs directory if it doesn't exist
mkdir -p logs
mkdir -p data

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    echo "Please install Python 3 first"
    exit 1
fi

echo "$(date) - Python 3 found: $(python3 --version)"

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "$(date) - Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
else
    echo "$(date) - Virtual environment already exists"
fi

# Activate virtual environment
echo "$(date) - Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Upgrade pip
echo "$(date) - Upgrading pip..."
pip install --upgrade pip --quiet

# Install dependencies
echo "$(date) - Installing dependencies from requirements.txt..."
pip install -r requirements.txt --quiet

# Prevent Python from writing bytecode files
export PYTHONDONTWRITEBYTECODE=1

# Run the integration
echo "$(date) - Running Firefly integration script..."
python firefly-integrator.py --config "$CONFIG_FILE" --credentials "$CREDENTIALS_FILE"

# Deactivate virtual environment
deactivate

echo "$(date) - Monobank->Firefly integration completed successfully"
