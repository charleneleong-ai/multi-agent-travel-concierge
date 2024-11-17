from typing import Optional
from datetime import datetime, timedelta
import requests
import os
from dotenv import load_dotenv
import json
import logging
from langchain.tools import StructuredTool

# Load environment variables
load_dotenv()

def search_hotels(
    location: str,
    check_in_date: Optional[str] = None,
    check_out_date: Optional[str] = None,
    adults: int = 1,
    children_age: str = "0,17",
    room_qty: int = 1,
    currency_code: str = "EUR"
) -> str:
    """
    Search for hotels in a given location.
    """
    # If dates not provided, use default dates
    if not check_in_date:
        check_in_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    if not check_out_date:
        check_out_date = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')

    # First, get coordinates for the location
    location_url = "https://booking-com15.p.rapidapi.com/api/v1/meta/locationToLatLong"
    headers = {
        "X-RapidAPI-Key": os.getenv("RAPIDAPI_KEY"),
        "X-RapidAPI-Host": "booking-com15.p.rapidapi.com"
    }
    
    try:
        # Get location coordinates
        location_response = requests.get(
            location_url, 
            headers=headers, 
            params={"query": location}
        )
        location_response.raise_for_status()
        location_data = location_response.json()
        
        if not location_data.get("data"):
            return f"No location data found for: {location}"
            
        latitude = location_data["data"][0]["geometry"]["location"]["lat"]
        longitude = location_data["data"][0]["geometry"]["location"]["lng"]
        
        # Search for hotels using coordinates
        hotel_url = "https://booking-com15.p.rapidapi.com/api/v1/hotels/searchHotelsByCoordinates"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "arrival_date": check_in_date,
            "departure_date": check_out_date,
            "adults": adults,
            "children_age": children_age,
            "room_qty": room_qty,
            "currency_code": currency_code,
            "units": "metric",
            "page_number": 1,
            "temperature_unit": "c",
            "languagecode": "en-us"
        }
        
        hotel_response = requests.get(hotel_url, headers=headers, params=params)
        hotel_response.raise_for_status()
        hotel_data = hotel_response.json()
        
        if not hotel_data.get("status", True):
            error_message = json.dumps(hotel_data.get("message", "Unknown error"), indent=2)
            return f"API returned error: {error_message}"
        
        if not hotel_data.get("data", {}).get("result"):
            return f"No hotels found in {location} for the specified dates"
            
        # Format the response
        result = [f"\nHotels found in {location}:"]
        result.append("-" * 50)
        
        for hotel in hotel_data["data"]["result"]:
            result.append(f"Hotel Name: {hotel.get('hotel_name', 'N/A')}")
            result.append(f"Review Score: {hotel.get('review_score', 'N/A')}")
            result.append(f"Review Score Word: {hotel.get('review_score_word', 'N/A')}")
            result.append(f"Total Price: {hotel.get('min_total_price', 'N/A')} {hotel.get('currencycode', 'N/A')}")
            result.append("-" * 50)
        
        return "\n".join(result)
            
    except Exception as e:
        logging.error(f"Error searching hotels: {str(e)}")
        return f"Error searching hotels: {str(e)}"

# Create a StructuredTool for CrewAI
hotel_tool = StructuredTool.from_function(
    func=search_hotels,
    name="search_hotels",
    description="""Search for hotels in a location. Use with these parameters:
    location: City or location name (e.g., 'Hassan', 'Singapore')
    check_in_date: Check-in date in YYYY-MM-DD format (optional, defaults to tomorrow)
    check_out_date: Check-out date in YYYY-MM-DD format (optional, defaults to day after tomorrow)
    adults: Number of adults (optional, default=1)
    children_age: Children ages (optional, default='0,17')
    room_qty: Number of rooms (optional, default=1)
    currency_code: Currency code (optional, default='EUR')""",
    return_direct=True
)

if __name__ == "__main__":
    # Example usage with all parameters
    location = "Singapore"
    check_in = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
    check_out = (datetime.now() + timedelta(days=10)).strftime('%Y-%m-%d')
    
    print(f"\nSearch Parameters:")
    print(f"Location: {location}")
    print(f"Check-in: {check_in}")
    print(f"Check-out: {check_out}")
    print("Adults: 2")
    print("Children Ages: 5,12")
    print("Room Quantity: 1")
    print("Currency: USD")
    print("Units: metric")
    print("Temperature Unit: Celsius")
    print("Language: English (US)")
    print("\nSearching...")
    
    results = search_hotels(
        location=location,
        check_in_date=check_in,
        check_out_date=check_out,
        adults=2,
        children_age="5,12",  # Two children aged 5 and 12
        room_qty=1,
        currency_code="USD"
    )
    
    print(results)
