using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Globalization;
using System.Net.Http;
using System.Text.Json;
using System.Threading.Tasks;
using Microsoft.SemanticKernel;
namespace BlazorAI.Plugins
{
    public class WeatherPlugin
    {
        private readonly IHttpClientFactory _httpClientFactory;
        public WeatherPlugin(IHttpClientFactory httpClientFactory)
        {
            _httpClientFactory = httpClientFactory;
        }
        [KernelFunction("GetWeatherForecast")]
        [Description("Get weather forecast for a location up to 16 days in the future")]
        public async Task<string> GetWeatherForecastAsync(
            [Description("Latitude of the location")] double latitude,
            [Description("Longitude of the location")] double longitude,
            [Description("Number of days to forecast (up to 16)")] int days = 16)
        {
            // Ensure days is within valid range (API supports up to 16 days)
            if (days > 16)
                days = 16;

            var url = $"https://api.open-meteo.com/v1/forecast" +
                    $"?latitude={latitude}&longitude={longitude}" +
                    $"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,weather_code" +
                    $"&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m" +
                    $"&temperature_unit=fahrenheit&wind_speed_unit=mph&precipitation_unit=inch" +
                    $"&forecast_days={days}&timezone=auto";
            try
            {
                var httpClient = _httpClientFactory.CreateClient();
                var response = await httpClient.GetAsync(url);
                response.EnsureSuccessStatusCode();
                var content = await response.Content.ReadAsStringAsync();
                var data = JsonDocument.Parse(content);
                // Extract daily forecast data
                var dailyElement = data.RootElement.GetProperty("daily");
                var times = dailyElement.GetProperty("time").EnumerateArray().ToArray();
                var maxTemps = dailyElement.GetProperty("temperature_2m_max").EnumerateArray().ToArray();
                var minTemps = dailyElement.GetProperty("temperature_2m_min").EnumerateArray().ToArray();
                var precipSums = dailyElement.GetProperty("precipitation_sum").EnumerateArray().ToArray();
                var precipProbs = dailyElement.GetProperty("precipitation_probability_max").EnumerateArray().ToArray();
                var weatherCodes = dailyElement.GetProperty("weather_code").EnumerateArray().ToArray();
                // Build a readable forecast for each day
                var forecasts = new List<object>();
                for (int i = 0; i < times.Length; i++)
                {
                    // Convert date string to DateTime object for day name
                    var dateStr = times[i].GetString();
                    var dateObj = DateTime.Parse(dateStr!);
                    var dayName = dateObj.ToString("dddd, MMMM dd", CultureInfo.InvariantCulture);
                    var weatherDesc = GetWeatherDescription(weatherCodes[i].GetInt32());
                    var forecast = new
                    {
                        date = dateStr,
                        day = dayName,
                        high_temp = $"{maxTemps[i]}°F",
                        low_temp = $"{minTemps[i]}°F", 
                        precipitation = $"{precipSums[i]} inches",
                        precipitation_probability = $"{precipProbs[i]}%",
                        conditions = weatherDesc
                    };
                    forecasts.Add(forecast);
                }
                var result = new
                {
                    location_coords = $"{latitude}, {longitude}",
                    forecast_days = forecasts.Count,
                    forecasts
                };
                // For more concise output in chat
                return JsonSerializer.Serialize(result, new JsonSerializerOptions { WriteIndented = true });
            }
            catch (Exception ex)
            {
                return $"Error fetching forecast weather: {ex.Message}";
            }
        }
        [KernelFunction("GetForecastWithPlugins")]
        [Description("Gets weather forecast for any location by coordinating with Time and Geocoding plugins.")]
        public async Task<string> GetForecastWithPluginsAsync(
            [Description("The kernel instance to use for calling other plugins")] Kernel kernel,
            [Description("The location name (city, address, etc.)")] string location,
            [Description("The day of the week to get forecast for, or number of days in future")] string daySpec = "0")
        {
            try
            {
                // Step 1: Get current date from Time Plugin
                var dateResult = await kernel.InvokeAsync("Time", "GetDate");
                string? todayStr = dateResult.GetValue<string>();
                if (todayStr == null)
                {
                    return "Could not determine the current date.";
                }
                DateTime today = DateTime.Parse(todayStr);
                
                // Step 2: Calculate target day based on specification
                int daysInFuture;
                if (int.TryParse(daySpec, out daysInFuture))
                {
                    // If daySpec is a number, use it directly
                }
                else if (Enum.TryParse<DayOfWeek>(daySpec, true, out var targetDay))
                {
                    // Calculate days until the next occurrence of the target day
                    daysInFuture = ((int)targetDay - (int)today.DayOfWeek + 7) % 7;
                    if (daysInFuture == 0) daysInFuture = 7; // If today is the target day, get next week
                }
                else
                {
                    return $"Invalid day specification: {daySpec}. Please provide a day name or number of days.";
                }
                // Step 3: Get location coordinates from Geocoding Plugin
                var locationResult = await kernel.InvokeAsync("Geocoding", "GetLocation", new() { ["location"] = location });
                string? locationJson = locationResult.GetValue<string>();
                
                if (locationJson == null)
                {
                    return $"Could not get location data for: {location}";
                }
                
                var locationData = JsonDocument.Parse(locationJson);
                double latitude, longitude;
                try {
                    latitude = locationData.RootElement.GetProperty("latitude").GetDouble();
                    longitude = locationData.RootElement.GetProperty("longitude").GetDouble();
                }
                catch (Exception)
                {
                    return $"Could not extract coordinates for location: {location}";
                }
                // Step 4: Get weather forecast
                return await GetWeatherForecastAsync(latitude, longitude, daysInFuture + 1);
            }
            catch (Exception ex)
            {
                return $"Error coordinating weather forecast: {ex.Message}";
            }
        }
        private string GetWeatherDescription(int code)
        {
            var weatherCodes = new Dictionary<int, string>
            {
                { 0, "Clear sky" },
                { 1, "Mainly clear" }, { 2, "Partly cloudy" }, { 3, "Overcast" },
                { 45, "Fog" }, { 48, "Depositing rime fog" },
                { 51, "Light drizzle" }, { 53, "Moderate drizzle" }, { 55, "Dense drizzle" },
                { 56, "Light freezing drizzle" }, { 57, "Dense freezing drizzle" },
                { 61, "Slight rain" }, { 63, "Moderate rain" }, { 65, "Heavy rain" },
                { 66, "Light freezing rain" }, { 67, "Heavy freezing rain" },
                { 71, "Slight snow fall" }, { 73, "Moderate snow fall" }, { 75, "Heavy snow fall" },
                { 77, "Snow grains" },
                { 80, "Slight rain showers" }, { 81, "Moderate rain showers" }, { 82, "Violent rain showers" },
                { 85, "Slight snow showers" }, { 86, "Heavy snow showers" },
                { 95, "Thunderstorm" }, { 96, "Thunderstorm with slight hail" }, { 99, "Thunderstorm with heavy hail" }
            };
            return weatherCodes.TryGetValue(code, out var description) ? description : "Unknown";
        }
    }
}