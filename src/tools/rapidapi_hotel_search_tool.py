import requests
import os
from dotenv import load_dotenv


# Load environment variables
load_dotenv()

def search_hotels_by_coordinates(latitude, longitude, adults=1, children_age="0,17", room_qty=1, units="metric", page_number=1, temperature_unit="c", languagecode="en-us", currency_code="EUR"):
   url = "https://booking-com15.p.rapidapi.com/api/v1/hotels/searchHotelsByCoordinates"
   headers = {
       "X-RapidAPI-Key": os.getenv("RAPIDAPI_KEY"),
       "X-RapidAPI-Host": "booking-com15.p.rapidapi.com"
   }
   params = {
       "latitude": latitude,
       "longitude": longitude,
       "adults": adults,
       "children_age": children_age,
       "room_qty": room_qty,
       "units": units,
       "page_number": page_number,
       "temperature_unit": temperature_unit,
       "languagecode": languagecode,
       "currency_code": currency_code
   }
   response = requests.get(url, headers=headers, params=params)
   return response.json()

def search_location_coordinates(location):
   url = "https://booking-com15.p.rapidapi.com/api/v1/meta/locationToLatLong"
   headers = {
       "X-RapidAPI-Key": os.getenv("RAPIDAPI_KEY"),
       "X-RapidAPI-Host": "booking-com15.p.rapidapi.com"
   }
   params = {
       "query": location
   }
   response = requests.get(url, headers=headers, params=params)
   return response.json()

# Example usage
location_response = search_location_coordinates("Hassan")
latitude = location_response["data"][0]["geometry"]["location"]["lat"]
longitude = location_response["data"][0]["geometry"]["location"]["lng"]

hotel_response = search_hotels_by_coordinates(latitude, longitude)

for hotel in hotel_response["data"]["result"]:
   print(f"Hotel Name: {hotel['hotel_name']}")
   print(f"Review Score: {hotel['review_score']}")
   print(f"Review Score Wording: {hotel['review_score_word']}")
   print(f"Total Price: {hotel['min_total_price']}")
   print()
