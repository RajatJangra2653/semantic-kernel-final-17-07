from typing import Annotated
import requests
from semantic_kernel.functions import kernel_function
import json
from datetime import datetime, timedelta

class WeatherPlugin:
    @kernel_function(description="Get weather forecast for a location up to 16 days in the future")
    def get_forecast_weather(self, 
                            latitude: Annotated[float, "Latitude of the location"],
                            longitude: Annotated[float, "Longitude of the location"],
                            days: Annotated[int, "Number of days to forecast (up to 16)"] = 16):
        
        # Ensure days is within valid range (API supports up to 16 days)
        if days > 16:
            days = 16
        
        url = (f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={latitude}&longitude={longitude}"
            f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,weather_code"
            f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m"
            f"&temperature_unit=fahrenheit&wind_speed_unit=mph&precipitation_unit=inch"
            f"&forecast_days={days}&timezone=auto")
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            daily = data.get('daily', {})
            times = daily.get('time', [])
            max_temps = daily.get('temperature_2m_max', [])
            min_temps = daily.get('temperature_2m_min', [])
            precip_sums = daily.get('precipitation_sum', [])
            precip_probs = daily.get('precipitation_probability_max', [])
            weather_codes = daily.get('weather_code', [])
            
            forecasts = []
            for i in range(len(times)):
                # Convert date string to datetime object for day name
                date_obj = datetime.strptime(times[i], "%Y-%m-%d")
                day_name = date_obj.strftime("%A, %B %d")
                
                weather_desc = self._get_weather_description(weather_codes[i])
                
                forecast = {
                    "date": times[i],
                    "day": day_name,
                    "high_temp": f"{max_temps[i]}°F",
                    "low_temp": f"{min_temps[i]}°F",
                    "precipitation": f"{precip_sums[i]} inches",
                    "precipitation_probability": f"{precip_probs[i]}%",
                    "conditions": weather_desc
                }
                forecasts.append(forecast)
            
            result = {
                "location_coords": f"{latitude}, {longitude}",
                "forecast_days": len(forecasts),
                "forecasts": forecasts
            }
            
            # For more concise output in chat
            return json.dumps(result, indent=2)
        except Exception as e:
            return f"Error fetching forecast weather: {str(e)}"
    
    def _get_weather_description(self, code):
        weather_codes = {
            0: "Clear sky",
            1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
            45: "Fog", 48: "Depositing rime fog",
            51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
            56: "Light freezing drizzle", 57: "Dense freezing drizzle",
            61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
            66: "Light freezing rain", 67: "Heavy freezing rain",
            71: "Slight snow fall", 73: "Moderate snow fall", 75: "Heavy snow fall",
            77: "Snow grains",
            80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
            85: "Slight snow showers", 86: "Heavy snow showers",
            95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail"
        }
        return weather_codes.get(code, "Unknown")