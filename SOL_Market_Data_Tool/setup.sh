#!/bin/bash

# SOL Market Data Tool Setup Script
# This script sets up the environment for the market data collector

echo "================================================"
echo "SOL Market Data Tool - Setup Script"
echo "================================================"
echo ""

# Check Python version
echo "Checking Python version..."
python3 --version
if [ $? -ne 0 ]; then
    echo "ERROR: Python 3 is not installed!"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

# Create virtual environment
echo ""
echo "Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Virtual environment created"
else
    echo "Virtual environment already exists"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo ""
echo "Installing requirements..."
pip install -r requirements.txt

if [ $? -eq 0 ]; then
    echo ""
    echo "================================================"
    echo "Setup completed successfully!"
    echo "================================================"
    echo ""
    echo "To start collecting data:"
    echo "1. Activate the virtual environment: source venv/bin/activate"
    echo "2. Run the collector: python collector.py"
    echo ""
    echo "Or use the launcher script: ./launch.sh start"
else
    echo ""
    echo "ERROR: Failed to install requirements"
    exit 1
fi

# Create data directory
if [ ! -d "sol_training_data" ]; then
    mkdir sol_training_data
    echo "Created data directory: sol_training_data/"
fi

# Make launcher executable
chmod +x launch.sh

echo ""
echo "Setup complete!"