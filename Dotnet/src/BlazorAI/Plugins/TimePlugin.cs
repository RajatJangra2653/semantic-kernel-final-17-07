using System;
using System.ComponentModel;
using System.Globalization;
using Microsoft.SemanticKernel;

namespace BlazorAI.Plugins
{
    public class TimePlugin
    {        
        [KernelFunction("current_time")]
        [Description("Gets the current date and time from the server. Use this directly when the user asks what time it is or wants to know the current date.")]
        public string CurrentTime()
        {
            return DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");
        }

        [KernelFunction("get_current_time")]
        [Description("Gets the current date and time from the server's system clock. Use this directly without asking the user for their location.")]
        public string GetCurrentTime()
        {
            return DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");
        }
        
        [KernelFunction("get_year")]
        [Description("Extract the year from a date string or get the current year from the system clock. Examples: 'What year is it now?' or 'What year is 2023-05-15?'")]
        public string GetYear(
            [Description("The date string. Accepts formats like YYYY-MM-DD, MM/DD/YYYY, etc. If not provided, uses the server's current date.")] 
            string? dateStr = null)
        {
            if (string.IsNullOrEmpty(dateStr))
            {
                return DateTime.Now.Year.ToString();
            }

            DateTime date;
            if (TryParseDate(dateStr, out date))
            {
                return date.Year.ToString();
            }
            
            return $"Could not parse '{dateStr}' as a valid date. Please provide a date in a standard format like YYYY-MM-DD or MM/DD/YYYY.";
        }
        
        [KernelFunction("get_month")]
        [Description("Extract the month name from a date string or get the current month from the system clock. Examples: 'What month is it now?' or 'What month is 2023-05-15?'")]
        public string GetMonth(
            [Description("The date string. Accepts formats like YYYY-MM-DD, MM/DD/YYYY, etc. If not provided, uses the server's current date.")] 
            string? dateStr = null)
        {
            if (string.IsNullOrEmpty(dateStr))
            {
                return DateTime.Now.ToString("MMMM");
            }
            
            DateTime date;
            if (TryParseDate(dateStr, out date))
            {
                return date.ToString("MMMM"); // Full month name
            }
            
            return $"Could not parse '{dateStr}' as a valid date. Please provide a date in a standard format like YYYY-MM-DD or MM/DD/YYYY.";
        }
        
        [KernelFunction("get_day_of_week")]
        [Description("Get the day of week from the server's system clock or for a specific date. Examples: 'What day is it today?' or 'What day of the week is 2023-05-15?'")]
        public string GetDayOfWeek(
            [Description("The date string. Accepts formats like YYYY-MM-DD, MM/DD/YYYY, etc. If not provided, uses the server's current date.")] 
            string? dateStr = null)
        {
            if (string.IsNullOrEmpty(dateStr))
            {
                return DateTime.Now.ToString("dddd");
            }
            
            DateTime date;
            if (TryParseDate(dateStr, out date))
            {
                return date.ToString("dddd"); // Full day name
            }
            
            return $"Could not parse '{dateStr}' as a valid date. Please provide a date in a standard format like YYYY-MM-DD or MM/DD/YYYY.";
        }

        private bool TryParseDate(string dateStr, out DateTime result)
        {
            string[] formats = { 
                "yyyy-MM-dd", "MM/dd/yyyy", "dd/MM/yyyy", 
                "M/d/yyyy", "d/M/yyyy", "MMM d, yyyy", 
                "MMMM d, yyyy", "yyyy/MM/dd", "dd-MMM-yyyy"
            };
            
            return DateTime.TryParseExact(
                dateStr, 
                formats, 
                CultureInfo.InvariantCulture,
                DateTimeStyles.None, 
                out result) || DateTime.TryParse(dateStr, out result);
        }
    }
}