#!/bin/bash
# Script to run Helios Server with proper Python environment

# Change to the app directory
cd /root/Desktop/Arsenal\ VPS/app

# Activate the virtual environment
source /root/Desktop/Arsenal\ VPS/activate_env.sh

# Run the helios server using the specific Python executable from the virtual environment
/root/Desktop/Arsenal\ VPS/venv/bin/python helios_server.py