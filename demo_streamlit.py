"""
demo_streamlit.py — Streamlit web interface for Mistral AI chat

Provides an interactive web UI for chatting with Mistral AI models.
Includes weather tool calling functionality and OpenTelemetry instrumentation.
Run with: streamlit run demo_streamlit.py
"""
import streamlit as st
import json
import urllib.request
import urllib.parse
from llm_client import chat, chat_with_tools, get_client
from prompts_loader import load_prompt
import config

# OpenTelemetry instrumentation for Streamlit UI events
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.streamlit import StreamlitInstrumentor
    
    # Set up OpenTelemetry tracing
    trace.set_tracer_provider(TracerProvider())
    otlp_exporter = OTLPSpanExporter(endpoint="http://localhost:4317", insecure=True)
    trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_exporter))
    
    # Instrument Streamlit
    StreamlitInstrumentor().instrument()
    
    # Get tracer for custom spans
    tracer = trace.get_tracer(__name__)
    
    def trace_streamlit_event(event_name: str, attributes: dict = None):
        """Create a custom span for Streamlit UI events."""
        with tracer.start_as_current_span(event_name) as span:
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, str(value))
    
except ImportError:
    # Fallback if OpenTelemetry is not available
    def trace_streamlit_event(event_name: str, attributes: dict = None):
        """No-op function if OpenTelemetry is not available."""
        pass


# --- Weather Tool Implementation (Open-Meteo — no API key needed) ------------

def _geocode(city: str) -> tuple[float, float, str]:
    """Resolve a city name to (latitude, longitude, resolved_name) via Open-Meteo geocoding."""
    params = urllib.parse.urlencode({"name": city, "count": 1, "language": "en", "format": "json"})
    url = f"https://geocoding-api.open-meteo.com/v1/search?{params}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.loads(resp.read())
    if not data.get("results"):
        raise ValueError(f"City not found: {city!r}")
    r = data["results"][0]
    return r["latitude"], r["longitude"], f"{r['name']}, {r.get('country', '')}"


def get_current_weather(location: str, format: str) -> str:
    """Fetch real current weather from Open-Meteo. No API key required."""
    city = location.split(",")[0].strip()
    lat, lon, resolved_name = _geocode(city)

    temperature_unit = "celsius" if format == "celsius" else "fahrenheit"
    params = urllib.parse.urlencode({
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
        "temperature_unit": temperature_unit,
        "wind_speed_unit": "kmh",
        "forecast_days": 1,
    })
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.loads(resp.read())

    current = data["current"]
    unit = "°C" if format == "celsius" else "°F"

    # WMO weather code → human-readable condition
    wmo_conditions = {
        0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Fog", 48: "Icy fog", 51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
        61: "Slight rain", 63: "Rain", 65: "Heavy rain", 71: "Slight snow", 73: "Snow",
        75: "Heavy snow", 80: "Slight showers", 81: "Showers", 82: "Heavy showers",
        95: "Thunderstorm", 99: "Thunderstorm with hail",
    }
    condition = wmo_conditions.get(current["weather_code"], f"Code {current['weather_code']}")

    return json.dumps({
        "location": resolved_name,
        "temperature": f"{current['temperature_2m']}{unit}",
        "feels_like": f"{current['apparent_temperature']}{unit}",
        "condition": condition,
        "wind_speed": f"{current['wind_speed_10m']} km/h",
    })


def tool_executor(name: str, args: dict) -> str:
    """Route tool calls to their implementations."""
    if name == "get_current_weather":
        return get_current_weather(**args)
    raise ValueError(f"Unknown tool: {name}")


# --- Tool definitions (sent to the model) ------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "Get the current weather for a city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city and country, e.g. Paris, France",
                    },
                    "format": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "Temperature unit. Infer from the user's location.",
                    },
                },
                "required": ["location", "format"],
            },
        },
    }
]


def main():
    # Trace the main function execution
    trace_streamlit_event("streamlit_main_start")
    
    st.set_page_config(page_title="Mistral AI Chat with Tools", layout="wide")
    st.title("🤖 Mistral AI Chat Demo with Weather Tools")
    
    # Welcome message with starter hint
    with st.expander("💡 Click here for a quick start guide", expanded=True):
        st.markdown("""
        **Welcome!** This demo lets you chat with Mistral AI and get real-time weather information.
        
        🌤️ **Try asking about the weather:**
        - "What's the weather in Paris?"
        - "Should I bring a jacket in London?"
        - "Compare weather in New York and Tokyo"
        
        💬 **Or ask anything else:**
        - "Tell me a joke"
        - "What's the capital of France?"
        - "Explain quantum computing simply"
        
        The AI will automatically use weather tools when needed!
        """)
    
    # Trace UI initialization
    trace_streamlit_event("ui_initialized")

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []
        trace_streamlit_event("chat_history_initialized")

    # Load system prompt
    system_message = load_prompt("system_prompt.txt")
    trace_streamlit_event("system_prompt_loaded")

    # Display chat messages from history on app rerun
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Accept user input
    if prompt := st.chat_input("What would you like to ask?"):
        # Trace user input event
        trace_streamlit_event("user_input_received", {
            "input_length": len(prompt),
            "input_type": "weather" if any(keyword in prompt.lower() for keyword in ["weather", "temperature", "forecast", "climate"]) else "general"
        })
        
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message in chat message container
        with st.chat_message("user"):
            st.markdown(prompt)

        # Display assistant response in chat message container
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            
            # Get response from AI - use tool calling if weather-related
            try:
                # Check if the prompt is weather-related
                weather_keywords = ["weather", "temperature", "forecast", "climate"]
                if any(keyword in prompt.lower() for keyword in weather_keywords):
                    # Trace weather tool usage
                    trace_streamlit_event("weather_tool_invoked", {
                        "user_query": prompt
                    })
                    # Use tool calling for weather questions
                    response = chat_with_tools(
                        user_message=prompt,
                        tools=TOOLS,
                        tool_executor=tool_executor,
                        system_message=system_message
                    )
                else:
                    # Trace regular chat usage
                    trace_streamlit_event("regular_chat_invoked", {
                        "user_query": prompt
                    })
                    # Use regular chat for other questions
                    response = chat(prompt, system_message=system_message)
                full_response = response
                message_placeholder.markdown(full_response)
                
                # Trace successful response
                trace_streamlit_event("response_completed", {
                    "response_length": len(full_response),
                    "response_type": "weather" if any(keyword in prompt.lower() for keyword in weather_keywords) else "general"
                })
                
            except Exception as e:
                message_placeholder.markdown(f"Error: {str(e)}")
                st.error(f"An error occurred: {str(e)}")
                # Trace error
                trace_streamlit_event("response_error", {
                    "error_message": str(e),
                    "error_type": type(e).__name__
                })

        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": full_response})
        trace_streamlit_event("chat_history_updated", {
            "total_messages": len(st.session_state.messages)
        })

    # Sidebar with configuration
    st.sidebar.title("⚙️ Configuration")
    st.sidebar.markdown(f"""
    **Current Settings:**
    - 🤖 Model: `{config.MISTRAL_MODEL}`
    - 🌡️ Temperature: `{config.MISTRAL_TEMPERATURE}`
    - 📝 Max Tokens: `{config.MISTRAL_MAX_TOKENS}`
    - 🎯 Top P: `{config.MISTRAL_TOP_P}`
    - 🔄 Max Retries: `{config.RETRY_MAX_ATTEMPTS}`
    """)
    st.sidebar.markdown("""
    ### How to Use
    1. Type your message in the input box at the bottom
    2. Press Enter to send
    3. The AI will respond conversationally
    4. Continue the conversation naturally
    """)
    st.sidebar.markdown("""
    ### Weather Examples
    Try these weather-related questions:
    - "What's the weather in Paris?"
    - "Should I bring a jacket in London?"
    - "Compare weather in New York and Tokyo"
    - "Is it sunny in Barcelona today?"
    """)
    st.sidebar.markdown("""
    ### 📝 Notes
    - The conversation history is maintained during this session
    - Refresh the page to start a new conversation
    - Weather data powered by **Open-Meteo** (free, no API key needed)
    """)
    
    st.sidebar.markdown("""
    ### 🔧 Model Parameters Explained
    - **Temperature**: Controls randomness (0.0 = deterministic, 2.0 = creative)
    - **Max Tokens**: Maximum response length
    - **Top P**: Nucleus sampling for diversity
    - **Max Retries**: How many times to retry failed requests
    """)
    
    st.sidebar.markdown("""
    ### 🔍 OpenTelemetry Tracing
    **Status:** `{}`
    
    This demo includes comprehensive tracing for observability:
    - 📊 **UI Events**: User interactions, chat flows
    - ⚡ **Performance**: Response times, processing duration  
    - 📈 **Usage**: Weather vs regular chat analytics
    - 🚨 **Errors**: Full error context and debugging
    
    **To view traces:**
    1. Start Jaeger: `docker run -d -p 16686:16686 -p 4317:4317 jaegertracing/all-in-one:latest`
    2. Open: [http://localhost:16686](http://localhost:16686)
    3. Filter by service: `demo_streamlit`
    """.format("✅ Active" if hasattr(trace, 'get_tracer_provider') else "❌ Disabled"))


if __name__ == "__main__":
    main()
