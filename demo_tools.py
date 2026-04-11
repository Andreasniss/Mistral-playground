"""
demo_tools.py — function calling demo

Shows how to define tools, let the model decide when to call them,
and feed results back for a final answer.

Uses Open-Meteo (https://open-meteo.com/) — free, no API key required.
Geocoding via Open-Meteo's geocoding API to resolve city names to lat/lon.
"""
import json
import urllib.request
import urllib.parse
from llm_client import chat_with_tools


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


# --- Tool implementation (Open-Meteo — no API key needed) --------------------

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


# --- Demo --------------------------------------------------------------------

def run():
    questions = [
        "What's the weather like today in Paris?",
        "Should I bring a jacket in London right now?",
        "Compare the weather in New York and Tokyo today.",
    ]

    for question in questions:
        print(f"\nUser: {question}")
        response = chat_with_tools(
            user_message=question,
            tools=TOOLS,
            tool_executor=tool_executor,
        )
        print(f"Assistant: {response}")
        print("-" * 60)


def interactive_mode():
    """Allow the user to ask about the weather in any city interactively."""
    print("\nInteractive Mode: Ask about the weather in any city!")
    print("Type 'exit' to quit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if user_input.lower() == "exit":
            break

        print(f"\nUser: {user_input}")
        response = chat_with_tools(
            user_message=user_input,
            tools=TOOLS,
            tool_executor=tool_executor,
        )
        print(f"Assistant: {response}")
        print("-" * 60)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        interactive_mode()
    else:
        run()
