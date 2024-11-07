from typing import Annotated, Literal
import asyncio
import os
from dotenv import load_dotenv
import logging
from pathlib import Path
import sys
from autogen import AssistantAgent, GroupChat, GroupChatManager, UserProxyAgent
from autogen.agentchat.contrib.capabilities.vision_capability import VisionCapability
from autogen.agentchat.contrib.multimodal_conversable_agent import MultimodalConversableAgent

# Add the src directory to Python path to import tools
src_path = str(Path(__file__).parent.parent.parent)
if src_path not in sys.path:
    sys.path.append(src_path)

# Import tools
from tools.rapidapi_flightsearch_detailed import search_flights
from tools.rapidapi_hotel_search_tool import search_hotels_by_coordinates, search_location_coordinates

# Load environment variables and configure logging
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Model configurations
config_list = [
    {
        "model": "gpt-4-turbo-preview",  # GPT-4 Turbo
        "api_key": os.getenv("OPENAI_API_KEY"),
        "temperature": 0.1,
    },
    {
        "model": "gpt-4",  # Standard GPT-4
        "api_key": os.getenv("OPENAI_API_KEY"),
        "temperature": 0.1,
    },
    {
        "model": "mixtral-8x7b-32768",  # Mixtral from Groq
        "api_key": os.getenv("GROQ_API_KEY"),
        "api_base": "https://api.groq.com/openai/v1",
        "api_type": "groq",
        "temperature": 0.1,
    },
    {
        "api_type": "bedrock",
        "model": "anthropic.claude-3-sonnet-20240229-v1:0",
        "aws_region": "us-east-1",
        "temperature": 0.1,
        "cache_seed": None,
    },
    {
        "api_type": "bedrock",
        "model": "anthropic.claude-3-haiku-20240307-v1:0",
        "aws_region": "us-east-1",
        "temperature": 0.1,
        "cache_seed": None,
    },
    {
        "api_type": "bedrock",
        "model": "amazon.titan-image-generator-v2:0",
        "aws_region": "us-east-1",
        "temperature": 0.1,
        "cache_seed": None,
    },
]

# Model selection strategies
PLANNER_CONFIG = config_list[:3]  # GPT-4s and Mixtral
ADVISOR_CONFIG = config_list[1:4]  # GPT-4 and Mixtral and Claude Sonnet
LOCAL_EXPERT_CONFIG = config_list[2:5]  # Mixtral and Claudes
MANAGER_CONFIG = config_list  # All models

def search_hotels_wrapper(location: str, **kwargs) -> str:
    """Wrapper function to combine location search and hotel search"""
    try:
        # First get coordinates
        location_data = search_location_coordinates(location)
        if not location_data.get("data"):
            return f"Could not find coordinates for location: {location}"
        
        latitude = location_data["data"][0]["geometry"]["location"]["lat"]
        longitude = location_data["data"][0]["geometry"]["location"]["lng"]
        
        # Then search hotels
        hotels = search_hotels_by_coordinates(
            latitude=latitude,
            longitude=longitude,
            **kwargs
        )
        
        if not hotels.get("data", {}).get("result"):
            return f"No hotels found in {location}"
        
        # Format results
        results = []
        for hotel in hotels["data"]["result"][:10]:  # Limit to top 10 hotels
            hotel_info = (
                f"\nHotel: {hotel['hotel_name']}\n"
                f"Rating: {hotel.get('review_score', 'N/A')} - {hotel.get('review_score_word', 'No reviews')}\n"
                f"Price: {hotel.get('min_total_price', 'N/A')} {kwargs.get('currency_code', 'EUR')}\n"
                f"Distance to center: {hotel.get('distance_to_cc', 'N/A')} km\n"
                f"Address: {hotel.get('address', 'N/A')}\n"
                f"Facilities: {', '.join(hotel.get('facilities', []))}\n"
                "---"
            )
            results.append(hotel_info)
            
        return "\n".join(results)
    except Exception as e:
        logger.error(f"Error searching for hotels: {str(e)}")
        return f"Error searching for hotels: {str(e)}"

# Tool configurations
TRAVEL_TOOLS = [
    {
        "name": "search_flights",
        "description": """Search for flights between cities with complete information.
        Required parameters:
        - from_city: Departure city airport code (e.g., 'BLR.AIRPORT')
        - to_city: Arrival city airport code (e.g., 'SIN.AIRPORT')
        - departure_date: Departure date in YYYY-MM-DD format
        - return_date: Return date in YYYY-MM-DD format
        
        Optional parameters:
        - adults: Number of adult passengers (default: 1)
        - children: Children ages (default: '0,17')
        - cabin_class: ECONOMY, PREMIUM_ECONOMY, BUSINESS, or FIRST (default: ECONOMY)
        - currency: Currency code (default: USD)""",
        "parameters": {
            "type": "object",
            "properties": {
                "from_city": {"type": "string"},
                "to_city": {"type": "string"},
                "departure_date": {"type": "string"},
                "return_date": {"type": "string"},
                "adults": {"type": "integer", "default": 1},
                "children": {"type": "string", "default": "0,17"},
                "cabin_class": {"type": "string", "default": "ECONOMY"},
                "currency": {"type": "string", "default": "USD"}
            },
            "required": ["from_city", "to_city", "departure_date", "return_date"]
        }
    },
    {
        "name": "search_hotels",
        "description": """Search for hotels in a specific location with detailed information.
        Required parameters:
        - location: Name of the city or location
        
        Optional parameters:
        - adults: Number of adults (default: 1)
        - children_age: Ages of children (default: '0,17')
        - room_qty: Number of rooms (default: 1)
        - currency_code: Currency for prices (default: EUR)""",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string"},
                "adults": {"type": "integer", "default": 1},
                "children_age": {"type": "string", "default": "0,17"},
                "room_qty": {"type": "integer", "default": 1},
                "currency_code": {"type": "string", "default": "EUR"}
            },
            "required": ["location"]
        }
    }
]

# Define agents
travel_planner = AssistantAgent(
    name="travel_planner",
    system_message="""You are a travel planner who can provide recommendations for flights and hotels based on the customer's preferences and budget. 
    You have access to real-time flight and hotel search capabilities. When searching:
    1. Always validate dates are in YYYY-MM-DD format
    2. Use proper airport codes (e.g., 'BLR.AIRPORT', 'SIN.AIRPORT')
    3. For hotels, provide clear price and rating information
    4. Consider distance to city center when recommending hotels
    5. Always provide baggage allowance and meal information for flights
    6. If dates aren't specified, ask for them and ensure they're in the future
    7. Consider the user's budget and preferences when making recommendations
    8. Explain any additional fees or charges that might apply""",
    llm_config={
        "config_list": PLANNER_CONFIG,
        "functions": TRAVEL_TOOLS
    }
)

legal_advisor = AssistantAgent(
    name="legal_advisor",
    system_message="""You are a legal advisor specializing in international travel regulations.
    Provide information on:
    1. Visa requirements and application processes
    2. Travel restrictions and entry requirements
    3. Health and vaccination requirements
    4. Customs regulations
    5. Travel insurance requirements
    6. Local laws and regulations that travelers should be aware of
    7. Required documentation for different types of travel""",
    llm_config={
        "config_list": ADVISOR_CONFIG,
    }
)

local_expert = AssistantAgent(
    name="local_expert",
    system_message="""You are a local expert with deep knowledge of various destinations.
    Provide advice on:
    1. Local customs and etiquette
    2. Best times to visit and seasonal considerations
    3. Local transportation options and how to use them
    4. Safety considerations and areas to avoid
    5. Must-see attractions and hidden gems
    6. Local cuisine and dining recommendations
    7. Cultural events and festivals
    8. Weather patterns and what to pack
    9. Local emergency services and healthcare facilities""",
    llm_config={
        "config_list": LOCAL_EXPERT_CONFIG,
    }
)

user_proxy = UserProxyAgent(
    name="user_proxy",
    system_message="""You help coordinate the travel planning process between the user and other agents.
    Your role is to:
    1. Ensure all necessary information is collected from the user
    2. Coordinate between different agents to create a comprehensive travel plan
    3. Ask for clarification when needed
    4. Summarize the final travel plan
    5. Handle any error scenarios gracefully""",
    human_input_mode="TERMINATE",
    max_consecutive_auto_reply=10,
    is_termination_msg=lambda x: x.get("content", "").rstrip().endswith("TERMINATE"),
    code_execution_config={
        "work_dir": "coding",
        "use_docker": False,
    }
)

# Set up the group chat
groupchat = GroupChat(
    agents=[travel_planner, legal_advisor, local_expert, user_proxy],
    messages=[],
    max_round=50
)

# Create the manager
manager = GroupChatManager(
    groupchat=groupchat,
    llm_config={
        "config_list": MANAGER_CONFIG,
    }
)

# Register tools with the user proxy
user_proxy.register_function(
    function_map={
        "search_flights": search_flights,
        "search_hotels": search_hotels_wrapper
    }
)

async def start_travel_planning(query: str):
    """Start a travel planning session with the provided query"""
    try:
        await user_proxy.initiate_chat(
            manager,
            message=query
        )
    except Exception as e:
        logger.error(f"Error in travel planning session: {str(e)}")
        return f"Error in travel planning: {str(e)}"

def get_travel_agents():
    """Returns the configured agents for external use"""
    return {
        "travel_planner": travel_planner,
        "legal_advisor": legal_advisor,
        "local_expert": local_expert,
        "user_proxy": user_proxy,
        "manager": manager
    }

if __name__ == "__main__":
    # Example in a qury
    query = """
    I need to plan a business trip to Singapore from New York:
    - Dates: March 20-25, 2024
    - Business class flights
    - Luxury hotel near Marina Bay
    - Need visa information for US citizens
    - Looking for good local restaurants
    Budget: $8000 for flights, $500/night for hotel
    """
    
    asyncio.run(start_travel_planning(query))