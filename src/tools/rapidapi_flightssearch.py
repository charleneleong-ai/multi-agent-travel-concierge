from typing import Optional, List
from datetime import datetime, timedelta
import requests
import os
from dotenv import load_dotenv
import json
from langchain.tools import StructuredTool

# Load environment variables
load_dotenv()

def get_nearest_airport(location: str) -> str:
    """
    Get the nearest airport code for a given location.
    Args:
        location (str): City name (e.g., 'Singapore', 'Milan')
    Returns:
        str: Airport code
    """
    url = "https://booking-com15.p.rapidapi.com/api/v1/flights/searchDestination"
    headers = {
        "X-RapidAPI-Key": os.getenv("RAPIDAPI_KEY"),
        "X-RapidAPI-Host": "booking-com15.p.rapidapi.com"
    }
    
    try:
        response = requests.get(url, headers=headers, params={"query": location})
        response.raise_for_status()
        data = response.json()
        
        if data.get("data") and len(data["data"]) > 0:
            return data["data"][0]["id"]
        return None
        
    except Exception as e:
        print(f"Error finding airport for {location}: {str(e)}")
        return None

def search_flights(
    from_location: str,
    to_location: str,
    departure_date: str,
    return_date: str,
    adults: int = 1,
    children_ages: List[int] = [],
    cabin_class: str = "ECONOMY",
    currency: str = "USD"
) -> str:
    """
    Search for flights between two locations.
    Args:
        from_location: Source city/location (e.g., 'Singapore')
        to_location: Destination city/location (e.g., 'Milan')
        departure_date: Departure date in YYYY-MM-DD format
        return_date: Return date in YYYY-MM-DD format
        adults: Number of adult passengers
        children_ages: List of children's ages [e.g., [2, 14] for 2 children aged 2 and 14]
        cabin_class: Cabin class (ECONOMY, BUSINESS, or FIRST)
        currency: Currency code for prices
    """
    
    # Get airport codes
    from_code = get_nearest_airport(from_location)
    if not from_code:
        return f"Could not find airport for {from_location}"
        
    to_code = get_nearest_airport(to_location)
    if not to_code:
        return f"Could not find airport for {to_location}"

    # Format children ages for API
    children_param = ",".join(map(str, children_ages)) if children_ages else "0,17"

    url = "https://booking-com15.p.rapidapi.com/api/v1/flights/searchFlightsMultiStops"
    
    # Create legs for round trip
    legs = [
        {
            "fromId": from_code,
            "toId": to_code,
            "date": departure_date
        },
        {
            "fromId": to_code,
            "toId": from_code,
            "date": return_date
        }
    ]

    querystring = {
        "legs": json.dumps(legs),
        "adults": str(adults),
        "children": children_param,
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

        if 'data' not in data or 'flightOffers' not in data['data']:
            return "No flights found."

        # Process and format flight offers
        result = []
        for offer in data['data']['flightOffers'][:10]:  # Limit to top 10 offers
            flight_info = parse_flight_offer(offer)
            if flight_info:
                result.append(flight_info)

        return "\n".join(result) if result else "No valid flight offers found."

    except Exception as e:
        return f"Error searching flights: {str(e)}"

def seconds_to_hhmm(seconds: int) -> str:
    """Convert seconds to HH:MM format"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours:02d}:{minutes:02d}"

def parse_flight_offer(offer):
    """Parse a single flight offer and return essential flight details"""
    try:
        carrier_name = offer['priceBreakdown']['carrierTaxBreakdown'][0]['carrier']['name']
        description = f"Flight Option by {carrier_name}:\n\n"

        # Process segments (journeys)
        for idx, segment in enumerate(offer['segments']):
            journey_type = "Outbound" if idx == 0 else "Return"
            description += f"{journey_type} Journey:\n"
            description += f"  From: {segment['departureAirport']['cityName']} ({segment['departureAirport']['code']})\n"
            description += f"  To: {segment['arrivalAirport']['cityName']} ({segment['arrivalAirport']['code']})\n"
            description += f"  Departure: {segment['legs'][0]['departureTime']}\n"
            description += f"  Arrival: {segment['legs'][0]['arrivalTime']}\n"
            description += f"  Duration: {seconds_to_hhmm(segment['totalTime'])}\n"
            description += f"  Flight Number: {segment['legs'][0]['flightInfo']['flightNumber']}\n"
            description += f"  Cabin Class: {segment['legs'][0]['cabinClass']}\n\n"

        # Add total price
        total_price = offer['priceBreakdown']['totalWithoutDiscountRounded']['units']
        currency = offer['priceBreakdown']['totalWithoutDiscountRounded']['currencyCode']
        description += f"Total Price: {total_price} {currency}\n"
        description += "-" * 50 + "\n"

        return description
    except Exception as e:
        return None

# Create the tool for CrewAI
flight_tool = StructuredTool.from_function(
    func=search_flights,
    name="search_flights",
    description="""Search for flights between two locations. 
    Parameters:
    - from_location: Source city/location (e.g., 'Singapore')
    - to_location: Destination city/location (e.g., 'Milan')
    - departure_date: Departure date in YYYY-MM-DD format
    - return_date: Return date in YYYY-MM-DD format
    - adults: Number of adult passengers (default=1)
    - children_ages: List of children's ages [e.g., [2, 14] for 2 children aged 2 and 14] (default=[])
    - cabin_class: ECONOMY/BUSINESS/FIRST (default='ECONOMY')
    - currency: Currency code (default='USD')""",
    return_direct=True
)

if __name__ == "__main__":
    # Example usage
    flights = search_flights(
        from_location="Singapore",
        to_location="Milan",
        departure_date=(datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'),
        return_date=(datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d'),
        adults=2,
        children_ages=[5, 12],
        cabin_class="ECONOMY",
        currency="USD"
    )
    print(flights)
