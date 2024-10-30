from typing import Optional, List
from datetime import datetime
import requests
import os
from dotenv import load_dotenv
import json
import logging
from langchain.tools import StructuredTool

# Load environment variables
load_dotenv()

def search_flights(
    from_city: str,
    to_city: str,
    departure_date: str,
    return_date: str,
    adults: int = 1,
    children: str = "0,17",
    cabin_class: str = "ECONOMY",
    currency: str = "USD"
) -> str:
    """
    Search for flights between two cities with specified dates and preferences.
    """
    url = "https://booking-com15.p.rapidapi.com/api/v1/flights/searchFlightsMultiStops"
    
    legs = [
        {
            "fromId": from_city,
            "toId": to_city,
            "date": departure_date
        },
        {
            "fromId": to_city,
            "toId": from_city,
            "date": return_date
        }
    ]

    querystring = {
        "legs": json.dumps(legs),
        "adults": str(adults),
        "children": children,
        "cabinClass": cabin_class,
        "currency_code": currency
    }

    headers = {
        "X-RapidAPI-Host": "booking-com15.p.rapidapi.com",
        "X-RapidAPI-Key": os.getenv("RAPIDAPI_KEY")
    }
    
    try:
        response = requests.get(url, headers=headers, params=querystring)
        response.raise_for_status()
        data = response.json()
        
        if 'data' in data and 'flightOffers' in data['data']:
            result = []
            for offer in data['data']['flightOffers']:
                flight_info = f"Flight Option:\n"
                # Onward Journey
                flight_info += f"Outbound: {offer['segments'][0]['departureAirport']['cityName']} to {offer['segments'][0]['arrivalAirport']['cityName']}\n"
                flight_info += f"Date: {offer['segments'][0]['legs'][0]['departureTime']}\n"
                flight_info += f"Airline: {offer['priceBreakdown']['carrierTaxBreakdown'][0]['carrier']['name']}\n"
                # Return Journey
                flight_info += f"Return: {offer['segments'][1]['departureAirport']['cityName']} to {offer['segments'][1]['arrivalAirport']['cityName']}\n"
                flight_info += f"Date: {offer['segments'][1]['legs'][0]['departureTime']}\n"
                # Price
                total_price = offer['priceBreakdown']['totalWithoutDiscountRounded']['units']
                currency = offer['priceBreakdown']['totalWithoutDiscountRounded']['currencyCode']
                flight_info += f"Total Price: {total_price} {currency}\n"
                flight_info += "-" * 50 + "\n"
                result.append(flight_info)
            
            return "\n".join(result)
        return "No flights found."
            
    except Exception as e:
        logging.error(f"Error searching flights: {str(e)}")
        return f"Error searching flights: {str(e)}"

# Create a StructuredTool for CrewAI
flight_tool = StructuredTool.from_function(
    func=search_flights,
    name="search_flights",
    description="""Search for flights between cities. Use with these parameters:
    from_city: Departure city airport code (e.g., 'BLR.AIRPORT')
    to_city: Arrival city airport code (e.g., 'SIN.AIRPORT')
    departure_date: Departure date in YYYY-MM-DD format
    return_date: Return date in YYYY-MM-DD format
    adults: Number of adult passengers (optional, default=1)
    children: Children ages (optional, default='0,17')
    cabin_class: Cabin class (optional, default='ECONOMY')
    currency: Currency code (optional, default='USD')""",
    return_direct=True
)
