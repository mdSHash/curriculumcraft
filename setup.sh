#!/bin/bash
set -e

echo "🧮 MathCraft — Setup Script"
echo "=========================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required. Install from https://python.org"
    exit 1
fi

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is required. Install from https://nodejs.org"
    exit 1
fi

echo "✓ Python $(python3 --version | cut -d' ' -f2) found"
echo "✓ Node.js $(node --version) found"
echo ""

# Backend setup
echo "📦 Setting up backend..."
cd backend

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -r requirements.txt --quiet

if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "  Created .env from template (edit to add your GEMINI_API_KEY)"
fi

mkdir -p data/uploads data/workbooks data/faiss_indices
cd ..

echo "✓ Backend ready"
echo ""

# Frontend setup
echo "📦 Setting up frontend..."
cd frontend
npm install --silent
cd ..

echo "✓ Frontend ready"
echo ""

echo "=========================="
echo "🎉 Setup complete!"
echo ""
echo "To start the app:"
echo "  Terminal 1: cd backend && source venv/bin/activate && uvicorn main:app --reload --port 8000"
echo "  Terminal 2: cd frontend && npm run dev"
echo ""
echo "Then open http://localhost:5173"
