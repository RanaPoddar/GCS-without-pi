#!/bin/bash

# Start script for GCS with PyMAVLink

echo "🚀 Starting Ground Control Station with PyMAVLink..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 is not installed"
    exit 1
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed"
    exit 1
fi

# Check/create virtual environment
if [ ! -d "myvenv" ]; then
    echo "📦 Creating virtual environment..."
    uv venv myvenv
fi

# Install Python dependencies using uv
echo "📦 Installing Python dependencies..."
uv pip install -r external-services/requirements.txt

# Install Node.js dependencies
if [ ! -d "node_modules" ]; then
    echo "📦 Installing Node.js dependencies..."
    npm install
fi

# Add axios if not already installed
npm list axios &> /dev/null || npm install axios

# Start PyMAVLink service in background (using venv Python)
echo "🐍 Starting PyMAVLink service..."
myvenv/bin/python external-services/pymavlink_service.py &
PYMAVLINK_PID=$!
echo "PyMAVLink service started with PID: $PYMAVLINK_PID"

# Wait for PyMAVLink service to be ready
echo "⏳ Waiting for PyMAVLink service to be ready..."
sleep 3

# Start Node.js server
echo "🚀 Starting Node.js Ground Control Station..."
node server.js &
SERVER_PID=$!
echo "GCS server started with PID: $SERVER_PID"

# Function to handle cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down services..."
    kill $PYMAVLINK_PID 2>/dev/null
    kill $SERVER_PID 2>/dev/null
    echo "✅ Services stopped"
    exit 0
}

# Register cleanup function for SIGINT and SIGTERM
trap cleanup SIGINT SIGTERM

echo ""
echo "✅ All services started!"
echo "📊 Mission Control: http://localhost:3000/mission-control"
echo "🎮 Landing Page: http://localhost:3000"
echo "🐍 PyMAVLink API: http://localhost:5000"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for both processes
wait
