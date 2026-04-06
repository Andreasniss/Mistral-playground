#!/bin/bash

# Step 1: Initialize the virtual environment
echo "🔥 Initializing virtual environment..."
source .venv/bin/activate
if [ $? -ne 0 ]; then
    echo "❌ Failed to activate virtual environment. Exiting."
    exit 1
fi
echo "✅ Virtual environment activated."

# Step 2: Check if Jaeger is running; if not, start it
echo "🔍 Checking Jaeger status..."
if ! docker ps | grep -q "jaeger"; then
    echo "🚀 Starting Jaeger for OpenTelemetry tracing..."
    docker run -d --name jaeger \
        -e COLLECTOR_OTLP_ENABLED=true \
        -p 16686:16686 \
        -p 4318:4318 \
        jaegertracing/all-in-one:latest
    if [ $? -ne 0 ]; then
        echo "❌ Failed to start Jaeger. Exiting."
        exit 1
    fi
    echo "✅ Jaeger started. Open http://localhost:16686 to view traces."
else
    echo "✅ Jaeger is already running."
fi

# Step 3: Run the demos
echo "🎤 Starting demo_chat.py (interactive chat)..."
echo "Type 'exit' to quit and proceed to the next demo."
python3 demo_chat.py

echo -e "\n🎤 Starting demo_tools.py (tool calling with weather API)..."
python3 demo_tools.py

echo -e "\n🎉 Demo complete! Check Jaeger at http://localhost:16686 for traces."