"""
Using RapidAPI to perform real-time hotel and flight information from booking.com
To access the playground to play around:
https://rapidapi.com/DataCrawler/api/booking-com15/playground/apiendpoint_818c2744-8507-4071-829e-d080b667a06c
"""

import os
from typing import Optional, List
from langchain.pydantic_v1 import BaseModel, Field
from langchain_core.tools import tool
import requests


class FlightLeg(BaseModel):
    fromId: str = Field(description="Departure airport code (IATA)")
    toId: str = Field(description="Arrival airport code (IATA)")
    date: str = Field(description="Flight date in the format YYYY-MM-DD.")


class FlightsInput(BaseModel):
    legs: List[FlightLeg] = Field(
        description="List of flight legs. Each leg must include departure, arrival, and date."
    )
    pageNo: Optional[int] = Field(
        1, description="Page number for the results, default is 1."
    )
    adults: Optional[int] = Field(
        1, description="Number of guests 18 years or older. Default is 1."
    )
    children: Optional[str] = Field(
        None,
        description="Ages of children, including infants, who are under 18. Example: '0,17' for a child of 17 years and an infant.",
    )
    sort: Optional[str] = Field(
        "BEST",
        description="Sort order of results, either 'BEST', 'CHEAPEST', or 'FASTEST'. Default is 'BEST'.",
    )
    cabinClass: Optional[str] = Field(
        "ECONOMY",
        description="Cabin class for the flight. Options: ECONOMY, PREMIUM_ECONOMY, BUSINESS, FIRST. Default is 'ECONOMY'.",
    )
    currency_code: Optional[str] = Field(
        "AED", description="Currency code for price display. Default is AED."
    )


class FlightsInputSchema(BaseModel):
    params: FlightsInput


@tool("flights-finder", args_schema=FlightsInputSchema)
def flights_finder(params: FlightsInput):
    """
    Find flights using the RapidAPI flight search engine.

    Returns:
        dict: Flight search results.
    """

    url = "https://booking-com15.p.rapidapi.com/api/v1/flights/searchFlightsMultiStops"

    querystring = {
        "legs": [
            {"fromId": leg.fromId, "toId": leg.toId, "date": leg.date}
            for leg in params.legs
        ],
        "pageNo": str(params.pageNo),
        "adults": str(params.adults),
        "children": params.children if params.children else "",
        "sort": params.sort,
        "cabinClass": params.cabinClass,
        "currency_code": params.currency_code,
    }

    headers = {
        "x-rapidapi-host": "booking-com15.p.rapidapi.com",
        "x-rapidapi-key": os.environ.get("RAPIDAPI_KEY"),
    }

    try:
        response = requests.get(url, headers=headers, params=querystring)
        response.raise_for_status()  # Raise an error for bad responses
        return response.json()  # Return the JSON data
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}
