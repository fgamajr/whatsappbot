#!/bin/bash

# Setup script for Interview Bot

set -e

echo "🚀 Setting up Interview Bot..."

# Create virtual environment
echo "📦 Creating virtual environment..."
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Copy environment file
if [ ! -f .env ]; then
    echo "📋 Creating .env file..."
    cp .env.example .env
    echo "⚠️  Please edit .env file with your actual credentials!"
fi

# Create logs directory
mkdir -p logs

echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your credentials"
echo "2. Set up MongoDB Atlas cluster"
echo "3. Run: source venv/bin/activate"
echo "4. Run: python -m app.main"
