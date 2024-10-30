from typing import Optional, List
from datetime import datetime, timedelta
# Update Pydantic imports to use v2
from pydantic import BaseModel, Field
from langchain_core.tools import tool
import requests
import os
from textwrap import dedent
from dotenv import load_dotenv
from langchain.tools import StructuredTool
import json
import logging

# Load environment variables
load_dotenv()

# Flight Search Models
class Leg(BaseModel):
    fromId: str = Field(description="Departure airport code (IATA)")
    toId: str = Field(description="Arrival airport code (IATA)")
    date: str = Field(description="Flight date in the format YYYY-MM-DD.")

class FlightsInput(BaseModel):
    legs: List[Leg]
    pageNo: int = 1
    adults: int = 1
    children: str = "0,17"
    sort: str = "BEST"
    cabinClass: str = "ECONOMY"
    currency_code: str = "USD"

    class Config:
        from_attributes = True

class FlightsInputSchema(BaseModel):
    params: FlightsInput

    class Config:
        from_attributes = True

# API Tools
def pounds_to_kg(weight_lb):
    """Convert weight from pounds to kilograms"""
    return round(weight_lb * 0.45359237, 1)

def seconds_to_hhmm(seconds: int) -> str:
    """Convert seconds to HH:MM format"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours:02d}:{minutes:02d}"

def parse_flight_offer(offer):
    """Parse a single flight offer and return structured data in a format suitable for LLM consumption"""
    try:
        carrier_name = offer['priceBreakdown']['carrierTaxBreakdown'][0]['carrier']['name']
        description = f"Flight Offer by {carrier_name}\n\n"

        # Process segments (journeys)
        for idx, segment in enumerate(offer['segments']):
            journey_type = "Onward" if idx == 0 else "Return"
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
                            # Handle cases where weight might be in different formats or missing
                            if 'maxTotalWeight' in bag_info:
                                weight_kg = pounds_to_kg(float(bag_info['maxTotalWeight']))
                                description += f"      Checked Baggage: {bag_info.get('maxPiece', 1)} piece(s), {weight_kg} KG\n"
                            else:
                                description += f"      Checked Baggage: {bag_info.get('maxPiece', 1)} piece(s)\n"
                        
                        elif product['type'] == 'cabinBaggage':
                            bag_info = product['product']
                            # Handle cases where weight might be in different formats or missing
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

def flights_finder(legs: List[dict], pageNo: int = 1, adults: int = 1, children: str = "0,17", 
                   sort: str = "BEST", cabinClass: str = "ECONOMY", currency_code: str = "USD"):
    """
    Find flights using the RapidAPI flight search engine.
    """
    logging.info(f"flights_finder called with: legs={legs}, adults={adults}, children={children}, cabinClass={cabinClass}, sort={sort}, currency_code={currency_code}")
    
    url = "https://booking-com15.p.rapidapi.com/api/v1/flights/searchFlightsMultiStops"

    legs_input = [Leg(**leg) for leg in legs]
    params = FlightsInput(legs=legs_input, pageNo=pageNo, adults=adults, children=children,
                          sort=sort, cabinClass=cabinClass, currency_code=currency_code)

    querystring = {
        "legs": json.dumps([leg.model_dump() for leg in params.legs]),
        "pageNo": str(params.pageNo),
        "adults": str(params.adults),
        "children": params.children,
        "sort": params.sort,
        "cabinClass": params.cabinClass,
        "currency_code": params.currency_code
    }

    headers = {
        "X-RapidAPI-Host": "booking-com15.p.rapidapi.com",
        "X-RapidAPI-Key": os.getenv("RAPIDAPI_KEY")
    }
    logging.info(f"API request URL: {url}")
    logging.info(f"API request headers: {headers}")
    logging.info(f"API request querystring: {querystring}")
    
    try:
        response = requests.get(url, headers=headers, params=querystring)
        response.raise_for_status()
        raw_response = response.json()
        
        if 'data' in raw_response and 'flightOffers' in raw_response['data']:
            descriptions = []
            for offer in raw_response['data']['flightOffers']:
                description = parse_flight_offer(offer)
                if description:
                    descriptions.append(description)
            return "\n".join(descriptions) if descriptions else "No flight offers found."
        else:
            return "No flight offers found in the response."
            
    except requests.exceptions.RequestException as e:
        logging.error(f"API request failed: {str(e)}")
        return f"Error: {str(e)}"
