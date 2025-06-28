#!/bin/bash

# Test script for Interview Bot

set -e

echo "🧪 Running tests..."

# Activate virtual environment
source venv/bin/activate

# Run tests
pytest tests/ -v --tb=short

# Run linting
echo "🔍 Running linting..."
black --check app/
mypy app/

echo "✅ All tests passed!"
