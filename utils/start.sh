#!/bin/bash
# LogSplitter Protobuf Ingestion Startup Script

echo "🚀 Starting LogSplitter Protobuf Ingestion System"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install requirements
echo "📥 Installing requirements..."
pip install -r requirements.txt

# Start the ingestion system
echo "▶️ Starting protobuf ingestion..."
python protobuf_ingestion.py