#!/bin/bash

# start_streamlit.sh — Launch Streamlit demo with full OpenTelemetry observability
# 
# This script starts:
# 1. Jaeger for distributed tracing
# 2. Streamlit web interface
# 3. Provides instructions for viewing traces

echo "🚀 Starting Streamlit Demo with Full Observability..."
echo ""

# Check if Docker is running
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker first."
    echo "   https://www.docker.com/get-started"
    exit 1
fi

# Start Jaeger for tracing
echo "🔍 Starting Jaeger for OpenTelemetry tracing..."
docker run -d -p 16686:16686 -p 4317:4317 --name mistral-jaeger jaegertracing/all-in-one:latest
if [ $? -ne 0 ]; then
    echo "❌ Failed to start Jaeger. Is Docker running?"
    exit 1
fi

# Give Jaeger a moment to start
sleep 2

# Check if Jaeger is accessible
JAEGER_URL="http://localhost:16686"
if curl --output /dev/null --silent --head --fail "$JAEGER_URL"; then
    echo "✅ Jaeger is running at $JAEGER_URL"
else
    echo "⚠️  Jaeger is starting... (may take a few seconds)"
fi

echo ""
echo "🎨 Starting Streamlit web interface..."
echo ""

# Activate virtual environment and start Streamlit
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi
.venv/bin/streamlit run demo_streamlit.py

echo ""
echo "📊 To view traces:"
echo "   Open your browser to: $JAEGER_URL"
echo "   Filter by service: 'demo_streamlit'"
echo ""
echo "💬 To stop everything when done:"
echo "   1. Press Ctrl+C in this terminal to stop Streamlit"
echo "   2. Run: docker stop mistral-jaeger && docker rm mistral-jaeger"
echo ""
echo "⚠️  Important: Closing the browser tab does NOT stop the server!"
echo "   Always use Ctrl+C to properly shut down Streamlit."
