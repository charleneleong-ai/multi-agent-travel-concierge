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
def flights_finder(legs: List[dict], pageNo: int = 1, adults: int = 1, children: str = "0,17", 
                   sort: str = "BEST", cabinClass: str = "ECONOMY", currency_code: str = "USD"):
    """
    Find flights using the RapidAPI flight search engine.
    """
    url = "https://booking-com15.p.rapidapi.com/api/v1/flights/searchFlightsMultiStops"

    legs_input = [Leg(**leg) for leg in legs]
    params = FlightsInput(legs=legs_input, pageNo=pageNo, adults=adults, children=children,
                          sort=sort, cabinClass=cabinClass, currency_code=currency_code)

    querystring = {
        "legs": json.dumps([leg.dict() for leg in params.legs]),
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

    try:
        response = requests.get(url, headers=headers, params=querystring)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

flights_finder_tool = StructuredTool.from_function(
    func=flights_finder,
    name="flights-finder",
    description="Find flights using the RapidAPI flight search engine. Input should be a list of legs, each containing fromId, toId, and date.",
)