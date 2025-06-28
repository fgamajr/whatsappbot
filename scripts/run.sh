#!/bin/bash

# Run script for Interview Bot

set -e

echo "🚀 Starting Interview Bot..."

# Activate virtual environment
source .venv/bin/activate

# Run with auto-reload in development
if [ "$1" = "dev" ]; then
    echo "🔄 Running in development mode with auto-reload..."
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
else
    echo "🏃 Running in production mode..."
    gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
fi
