from langchain.tools import BaseTool, StructuredTool
import requests
import os
from dotenv import load_dotenv
from typing import ClassVar, Optional

# Load environment variables from a .env file
load_dotenv()

class SearchAttractionTool(BaseTool):
    name: ClassVar[str] = "Search Attraction Tool"
    description: ClassVar[str] = "Searches for attractions in a given location using the Booking API and returns the response in markdown format."
    api_key: str = None

    def __init__(self):
        super().__init__()
        self.api_key = os.getenv("RAPIDAPI_KEY")

    def _run(self, query: str) -> str:
        if not self.api_key:
            return "API key not found. Please set the RAPIDAPI_KEY environment variable."

        url = "https://booking-com15.p.rapidapi.com/api/v1/attraction/searchLocation"
        headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": "booking-com15.p.rapidapi.com"
        }
        params = {
            "query": query,
            "languagecode": "en-us"
        }

        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            return f"Error: {response.status_code}. Unable to fetch data."

        data = response.json()

        # Parse and format the response in markdown
        attractions = data.get("data", {}).get("products", [])
        if not attractions:
            return "No attractions found for the specified location."

        markdown_response = f"# Attractions in {query.title()}\n"
        for i, attraction in enumerate(attractions):
            title = attraction.get("title", "No title available")
            markdown_response += f"**{i+1}. {title}**\n\n"

        return markdown_response

def search_attractions(location: str) -> str:
    """Search for attractions in a given location"""
    api_key = os.getenv("RAPIDAPI_KEY")
    
    if not api_key:
        return "API key not found. Please set the RAPIDAPI_KEY environment variable."

    url = "https://booking-com15.p.rapidapi.com/api/v1/attraction/searchLocation"
    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": "booking-com15.p.rapidapi.com"
    }
    params = {
        "query": location,
        "languagecode": "en-us"
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        attractions = data.get("data", {}).get("products", [])
        if not attractions:
            return "No attractions found for the specified location."

        result = [f"\nAttractions in {location}:"]
        result.append("-" * 50)
        
        for i, attraction in enumerate(attractions[:5]):  # Show top 5 attractions
            result.append(f"Name: {attraction.get('title', 'N/A')}")
            result.append("-" * 50)

        return "\n".join(result)
    
    except Exception as e:
        return f"Error searching attractions: {str(e)}"

# Create StructuredTool for attractions
attraction_tool = StructuredTool.from_function(
    func=search_attractions,
    name="search_attractions",
    description="Search for tourist attractions in a given location. Parameters: location (str): Name of the city or location",
    return_direct=True
)
