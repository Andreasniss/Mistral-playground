# 🎨 Streamlit Web Demo (Recommended)

The most impressive and user-friendly way to demonstrate the Mistral API is through the interactive Streamlit web interface.

## 🚀 Quick Start

```bash
# Easy way - use the startup script
bash start_streamlit.sh

# Or manually
docker run -d -p 16686:16686 -p 4317:4317 jaegertracing/all-in-one:latest
.venv/bin/streamlit run demo_streamlit.py
```

## 🌟 Key Features to Demonstrate

### 1. **Interactive Chat Interface**
- Modern web UI with chat bubbles
- Conversation history maintained during session
- Real-time responses
- Professional, polished appearance

### 2. **Weather Tool Integration**
**Impressive examples to try:**
- "What's the current weather in Paris?"
- "Should I bring a jacket in London today?"
- "Compare the weather in New York and Tokyo"
- "Is it sunny in Barcelona right now?"

**What happens:**
1. User asks weather question
2. AI automatically detects weather intent
3. Calls Open-Meteo API (no API key needed!)
4. Returns formatted weather data with temperature, conditions, wind speed
5. All tracked in Jaeger for observability

### 3. **Complete Observability**
- **OpenTelemetry instrumentation** throughout
- **Jaeger tracing** for both UI and API calls
- **Performance metrics** visible in real-time
- **Error tracking** with full context

**Show them:**
1. Open Jaeger at `http://localhost:16686`
2. Filter by service: `demo_streamlit`
3. Show the end-to-end trace from UI click → Mistral API → Weather tool → Response
4. Demonstrate error tracking by asking an invalid question

### 4. **Configuration Transparency**
The sidebar shows all current settings:
- 🤖 Model: `mistral-large-latest`
- 🌡️ Temperature: `0.0` (deterministic)
- 📝 Max Tokens: `1024`
- 🎯 Top P: `None`
- 🔄 Max Retries: `3`

### 5. **Built-in Documentation**
- Starter guide with examples
- Weather tool explanations
- OpenTelemetry status indicator
- Parameter explanations

## 🎯 Interview Talking Points

### Why This is Impressive

1. **Production-Ready Architecture**
   - Clean separation of concerns
   - Proper error handling
   - Observability built-in
   - Configuration management

2. **Modern Stack**
   - Streamlit for rapid UI development
   - OpenTelemetry for observability
   - Jaeger for distributed tracing
   - Mistral API for AI power

3. **Real-World Integration**
   - Weather API integration (Open-Meteo)
   - Tool calling pattern
   - Async capabilities
   - State management

4. **Developer Experience**
   - Easy to understand code
   - Good documentation
   - Helpful error messages
   - Graceful degradation

### What to Emphasize

✅ **"This is how we build production AI applications"**
- Not just a CLI demo, but a real web interface
- Complete observability stack
- Proper error handling and monitoring

✅ **"Look at the end-to-end tracing"**
- Show Jaeger traces from UI click to API response
- Demonstrate how you can debug issues
- Show performance metrics

✅ **"The weather tool shows function calling"**
- Explain how the AI decides when to use tools
- Show the tool definition and implementation
- Demonstrate the seamless integration

✅ **"Everything is configurable and observable"**
- Point out the sidebar configuration
- Show how easy it is to change parameters
- Emphasize the transparency

## 📋 Demo Script

### 1. Introduction (30 seconds)
"Let me show you our production-ready Mistral AI interface. This Streamlit application demonstrates how we build real-world AI applications with proper observability and tool integration."

### 2. Basic Chat (1 minute)
- Ask: "Tell me a joke"
- Show the response
- Point out the clean UI and conversation history

### 3. Weather Tool (2 minutes) - **This is the wow factor!**
- Ask: "What's the weather in Paris?"
- While it's processing: "Notice how the AI automatically detects this is a weather question and uses the weather tool..."
- Show the formatted response
- Ask: "Compare weather in New York and Tokyo"
- Point out it handles multiple cities

### 4. Observability (2 minutes)
- Open Jaeger in browser
- Show the traces: "Here you can see the complete flow..."
- Point out UI events, API calls, tool executions
- Show performance metrics
- Demonstrate error handling by asking invalid question

### 5. Architecture (1 minute)
- Show the code structure
- Explain the separation of concerns
- Point out the OpenTelemetry instrumentation
- Mention the configuration management

### 6. Wrap-up (30 seconds)
"This demonstrates how we build production AI applications: clean architecture, proper observability, tool integration, and great user experience. The same patterns scale to enterprise applications."

## ⚠️ Common Issues & Fixes

### "Streamlit won't start"
- **Check**: `.venv/bin/streamlit` exists
- **Fix**: `pip install streamlit`

### "Jaeger not accessible"
- **Check**: `docker ps` shows jaeger container
- **Fix**: `docker run -d -p 16686:16686 -p 4317:4317 jaegertracing/all-in-one:latest`

### "No traces in Jaeger"
- **Check**: Jaeger URL is `http://localhost:16686`
- **Fix**: Wait 30 seconds, refresh browser

### "Weather data not working"
- **Check**: Internet connection
- **Fix**: Open-Meteo is free and reliable, but check your network

## 💡 Pro Tips

1. **Prepare your environment**
   - Start Jaeger before the interview
   - Have Streamlit ready to launch
   - Test with a weather question first

2. **Have backup examples**
   - "What's the weather in [your city]?"
   - "Should I wear a coat in Berlin?"
   - "Is it raining in London?"

3. **Show the code**
   - Be ready to show `demo_streamlit.py`
   - Point out the OpenTelemetry instrumentation
   - Show the weather tool implementation

4. **Emphasize best practices**
   - Error handling
   - Configuration management
   - Observability
   - Separation of concerns

## 🎬 Practice Your Demo

1. **Time yourself** - Keep it under 5 minutes
2. **Practice the script** - Make it sound natural
3. **Prepare for questions** - Know the code inside out
4. **Have a backup** - If internet fails, show CLI demos

This Streamlit demo will impress interviewers by showing you understand production AI development, not just API calls!