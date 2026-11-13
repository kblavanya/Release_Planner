# Production deployment script for Windows

Write-Host "🚀 Starting Release Planning Application Deployment..." -ForegroundColor Green

# Check if .env file exists
if (!(Test-Path ".env")) {
    Write-Host "❌ Error: .env file not found!" -ForegroundColor Red
    Write-Host "Please create .env file from env.template" -ForegroundColor Red
    exit 1
}

# Create virtual environment if it doesn't exist
if (!(Test-Path "venv")) {
    Write-Host "📦 Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
}

# Activate virtual environment
Write-Host "🔧 Activating virtual environment..." -ForegroundColor Yellow
& "venv\Scripts\Activate.ps1"

# Install production requirements
Write-Host "📥 Installing production requirements..." -ForegroundColor Yellow
pip install -r requirements.txt

# Start the application with Waitress (Windows-friendly WSGI server)
Write-Host "🌟 Starting application with Waitress..." -ForegroundColor Green
waitress-serve --host=0.0.0.0 --port=5000 wsgi:app

Write-Host "✅ Deployment completed!" -ForegroundColor Green
Write-Host "Application should be running on http://localhost:5000" -ForegroundColor Green
