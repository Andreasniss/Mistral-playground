#!/usr/bin/env fish

# start_streamlit.fish — Launch Streamlit demo with full OpenTelemetry observability
# 
# This script starts:
# 1. Jaeger for distributed tracing
# 2. Streamlit web interface
# 3. Provides instructions for viewing traces

echo "🚀 Starting Streamlit Demo with Full Observability..."
echo ""

# Check if Docker is running
set docker_available
if command -v docker >/dev/null 2>&1
    set docker_available 1
else
    echo "⚠️  Docker not found. Continuing without Jaeger tracing."
    echo "   Install Docker for full observability: https://www.docker.com/get-started"
    echo ""
    set docker_available 0
end

# Start Jaeger for tracing if Docker is available
if test $docker_available -eq 1
    echo "🔍 Starting Jaeger for OpenTelemetry tracing..."

    # Check if Jaeger is already running
    if docker ps -a --format '{{.Names}}' | grep -q "mistral-jaeger"
        echo "✅ Jaeger container already exists"
        # Start the container if it's stopped
        if docker inspect -f '{{.State.Running}}' mistral-jaeger | string match -q "false"
            echo "🔄 Starting existing Jaeger container..."
            docker start mistral-jaeger
        else
            echo "✅ Jaeger is already running"
        end
    else
        # Start new container
        docker run -d -p 16686:16686 -p 4317:4317 --name mistral-jaeger jaegertracing/all-in-one:latest
        if test $status -ne 0
            echo "❌ Failed to start Jaeger. Is Docker running?"
            exit 1
        end
    end

    # Give Jaeger a moment to start
    sleep 2

    # Check if Jaeger is accessible
    set jaeger_url "http://localhost:16686"
    if curl --output /dev/null --silent --head --fail "$jaeger_url"
        echo "✅ Jaeger is running at $jaeger_url"
    else
        echo "⚠️  Jaeger is starting... (may take a few seconds)"
    end
    set jaeger_url "http://localhost:16686"
else
    set jaeger_url "N/A (Docker not available)"
end

echo ""
echo "🎨 Starting Streamlit web interface..."
echo ""

# Activate virtual environment and start Streamlit
source .venv/bin/activate.fish 2>/dev/null || source .venv/bin/activate
.venv/bin/streamlit run demo_streamlit.py

echo ""
if test $docker_available -eq 1
    echo "📊 To view traces:"
    echo "   Open your browser to: $jaeger_url"
    echo "   Filter by service: 'demo_streamlit'"
    echo ""
    echo "💬 To stop everything when done:"
    echo "   1. Press Ctrl+C in this terminal to stop Streamlit"
    echo "   2. Run: docker stop mistral-jaeger && docker rm mistral-jaeger"
else
    echo "📊 Tracing is disabled (Docker not available)"
    echo "   Install Docker to enable full observability"
    echo ""
    echo "💬 To stop when done:"
    echo "   Press Ctrl+C in this terminal to stop Streamlit"
end
echo ""
echo "⚠️  Important: Closing the browser tab does NOT stop the server!"
echo "   Always use Ctrl+C to properly shut down Streamlit."
