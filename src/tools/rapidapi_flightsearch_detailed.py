from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
import requests
import os
from dotenv import load_dotenv
import json
import logging
from langchain.tools import StructuredTool

# Load environment variables
load_dotenv()

# Helper functions
def pounds_to_kg(weight_lb):
    """Convert weight from pounds to kilograms"""
    return round(weight_lb * 0.45359237, 1)

def seconds_to_hhmm(seconds: int) -> str:
    """Convert seconds to HH:MM format"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours:02d}:{minutes:02d}"

def parse_flight_offer(offer):
    """Parse a single flight offer and return structured data"""
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
            description += f"  Cabin Class: {segment['legs'][0]['cabinClass']}\n"

            # Add meal information if available
            meal_info = next((a for a in segment['legs'][0].get('amenities', []) 
                            if a['category'] == 'FOOD'), None)
            if meal_info:
                meal_type = meal_info.get('type', 'Available')
                meal_cost = f" ({meal_info['cost']})" if 'cost' in meal_info else ""
                description += f"  Meal Service: {meal_type}{meal_cost}\n"

            # Process baggage information
            description += f"\n  {journey_type} Journey Baggage Allowance:\n"
            included_products = offer.get('includedProductsBySegment', [])
            if included_products and len(included_products) > idx:
                for traveller_info in included_products[idx]:
                    traveller_ref = traveller_info['travellerReference']
                    description += f"\n    Traveller {traveller_ref}:\n"
                    
                    for product in traveller_info['travellerProducts']:
                        if product['type'] == 'checkedInBaggage':
                            bag_info = product['product']
                            if 'maxTotalWeight' in bag_info:
                                weight_kg = pounds_to_kg(float(bag_info['maxTotalWeight']))
                                description += f"      Checked Baggage: {bag_info.get('maxPiece', 1)} piece(s), {weight_kg} KG\n"
                            else:
                                description += f"      Checked Baggage: {bag_info.get('maxPiece', 1)} piece(s)\n"
                        
                        elif product['type'] == 'cabinBaggage':
                            bag_info = product['product']
                            if 'maxWeightPerPiece' in bag_info:
                                weight_kg = pounds_to_kg(float(bag_info['maxWeightPerPiece']))
                                description += f"      Cabin Baggage: {bag_info.get('maxPiece', 1)} piece(s), {weight_kg} KG\n"
                            else:
                                description += f"      Cabin Baggage: {bag_info.get('maxPiece', 1)} piece(s)\n"
                            
                            if 'sizeRestrictions' in bag_info:
                                size = bag_info['sizeRestrictions']
                                description += f"      Size Limits: {size['maxLength']}x{size['maxWidth']}x{size['maxHeight']} {size['sizeUnit']}\n"
                        
                        elif product['type'] == 'personalItem':
                            description += "      Personal Item: Included\n"
            description += "\n"

        # Process traveller prices
        description += "Pricing Details by Traveller:\n"
        for price_info in offer['travellerPrices']:
            traveller_ref = price_info['travellerReference']
            traveller_type = price_info['travellerType']
            price_breakdown = price_info['travellerPriceBreakdown']
            base_fare = price_breakdown['baseFare']['units']
            tax = price_breakdown['tax']['units']
            total = price_breakdown['totalWithoutDiscountRounded']['units']
            currency = price_breakdown['totalWithoutDiscountRounded']['currencyCode']
            
            description += f"  Traveller {traveller_ref} ({traveller_type}):\n"
            description += f"    Base Fare: {base_fare} {currency}\n"
            description += f"    Tax: {tax} {currency}\n"
            description += f"    Total: {total} {currency}\n"

        # Total price
        total_price = offer['priceBreakdown']['totalWithoutDiscountRounded']['units']
        currency = offer['priceBreakdown']['totalWithoutDiscountRounded']['currencyCode']
        description += f"\nTotal Price: {total_price} {currency}\n"
        description += "-" * 80 + "\n"

        return description
    except Exception as e:
        logging.error(f"Error parsing flight offer: {str(e)}")
        return None

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
                flight_info = parse_flight_offer(offer)
                if flight_info:
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
