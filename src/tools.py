"""
Tool definitions and implementations.
"""

import json
from typing import Any


# Tool definition for the API
GET_WEATHER_TOOL = {
    "name": "get_weather",
    "description": "Get the current weather for a location",
    "input_schema": {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "City name or coordinates (e.g., 'San Francisco' or '37.7749°N, 122.4194°W')"
            }
        },
        "required": ["location"]
    }
}


def get_weather(location: str) -> dict:
    """
    Dummy implementation of get_weather.
    In a real app, this would call a weather API.
    """
    # Simulated responses based on location
    weather_data = {
        "San Francisco": {"temp": 62, "condition": "Cloudy", "humidity": 75},
        "New York": {"temp": 55, "condition": "Rainy", "humidity": 85},
        "London": {"temp": 50, "condition": "Overcast", "humidity": 80},
        "Tokyo": {"temp": 68, "condition": "Clear", "humidity": 60},
    }

    result = weather_data.get(
        location,
        {"temp": 70, "condition": "Unknown", "humidity": 50}
    )

    return {
        "location": location,
        **result
    }


def run_tool(tool_name: str, tool_input: dict) -> str:
    """
    Run a tool by name and return the JSON result.

    Args:
        tool_name: Name of the tool to run
        tool_input: Dictionary of input parameters

    Returns:
        JSON string with the tool result
    """
    if tool_name == "get_weather":
        result = get_weather(tool_input.get("location", "Unknown"))
        return json.dumps(result)

    else:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
