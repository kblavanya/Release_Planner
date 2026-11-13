#!/bin/bash
# Production deployment script for Linux/Unix systems

set -e

echo "🚀 Starting Release Planning Application Deployment..."

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found!"
    echo "Please create .env file from env.template"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install production requirements
echo "📥 Installing production requirements..."
pip install -r requirements.txt

# Run database migrations if any (placeholder)
echo "🗄️ Running any database migrations..."
# Add migration commands here if needed

# Start the application with Gunicorn
echo "🌟 Starting application with Gunicorn..."
gunicorn --config gunicorn.conf.py wsgi:app

echo "✅ Deployment completed!"
echo "Application should be running on http://0.0.0.0:5000"
