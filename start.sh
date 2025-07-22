#!/bin/sh

# Create data directories if they don't exist (with error handling)
mkdir -p /app/data/geoip 2>/dev/null || true
mkdir -p /app/data/geosite 2>/dev/null || true
mkdir -p /app/logs 2>/dev/null || true

# Start the application
cd /app
python -m src.main 