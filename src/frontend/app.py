import streamlit as st
from datetime import datetime, timedelta
import json
from typing import Dict, Any
from src.llm.llm_factory import LLMFactory
from src.llm.prompt_templates import TRAVEL_PROMPT
import os
import requests
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class ModernTravelPlannerApp:
    def __init__(self):
        self.initialize_session_state()
        self.llm = self.initialize_llm()
        
    def initialize_session_state(self):
        """Initialize session state variables"""
        if 'travel_details' not in st.session_state:
            default_start = datetime.now() + timedelta(days=10)
            default_end = default_start + timedelta(days=7)
            
            st.session_state.travel_details = {
                'natural_input': '',
                'dates': {
                    'departure': default_start.strftime('%Y-%m-%d'),
                    'return': default_end.strftime('%Y-%m-%d')
                },
                'parsed_details': None,
                'duration_days': None
            }
        if 'llm_provider' not in st.session_state:
            st.session_state.llm_provider = 'Ollama'
        if 'ollama_model' not in st.session_state:
            st.session_state.ollama_model = 'llama3.2:1b'

    def initialize_llm(self):
        """Initialize LLM based on selected provider"""
        return LLMFactory.create_llm(st.session_state.llm_provider)

    def render_header(self):
        """Render modern header with LLM selection"""
        st.title("✈️ AI Travel Planner")
        
        # Modern sidebar for configurations
        with st.sidebar:
            st.header("🛠️ Configuration")
            selected_llm = st.selectbox(
                "Select AI Model",
                options=['Ollama', 'Groq'],
                index=0
            )
            
            # Model selection based on provider
            if selected_llm == 'Ollama':
                st.session_state.ollama_model = st.selectbox(
                    "Select Ollama Model",
                    options=['llama3.2:1b'],
                    index=0
                )
                
                # Add Ollama status check with model-specific information
                if st.button("Check Ollama Status"):
                    try:
                        # Check if Ollama is running
                        response = requests.get("http://localhost:11434/api/version")
                        if response.status_code == 200:
                            st.success("✅ Ollama service is running")
                            
                            # Check if the model is pulled
                            model_response = requests.post(
                                "http://localhost:11434/api/show",
                                json={"name": "llama3.2:1b"}
                            )
                            if model_response.status_code == 200:
                                st.success("✅ Model llama3.2:1b is available")
                            else:
                                st.error("""
                                ❌ Model not found. Please pull the model:
                                ```bash
                                ollama pull llama3.2:1b
                                ```
                                """)
                        else:
                            st.error("❌ Ollama is not responding")
                    except:
                        st.error("""
                        ❌ Ollama is not running. Please:
                        1. Install Ollama from https://ollama.ai
                        2. Start the Ollama service
                        3. Pull the model: ollama pull llama3.2:1b
                        """)
            
            elif selected_llm == 'Groq':
                st.session_state.groq_model = st.selectbox(
                    "Select Groq Model",
                    options=[
                        'mixtral-8x7b-32768',
                        'llama2-70b-4096',
                        'gemma-7b-it'
                    ],
                    index=0
                )
                # Add API key input for Groq
                api_key = st.text_input(
                    "Groq API Key",
                    type="password",
                    value=os.getenv("GROQ_API_KEY", ""),
                    help="Enter your Groq API key. It will not be stored permanently."
                )
                if api_key:
                    os.environ["GROQ_API_KEY"] = api_key
            
            if selected_llm != st.session_state.llm_provider:
                st.session_state.llm_provider = selected_llm
                try:
                    self.llm = self.initialize_llm()
                except Exception as e:
                    st.error(f"Error initializing {selected_llm}: {str(e)}")
                    # Fallback to Ollama
                    st.session_state.llm_provider = 'Ollama'
                    self.llm = self.initialize_llm()

    def render_natural_input(self):
        """Capture travel details through natural language"""
        st.write("### Tell me about your dream trip ✨")
        
        example_text = """
        Example: I want to plan a luxury vacation from New York to Paris for 2 adults 
        and 1 child. We're interested in art museums, fine dining, and shopping. 
        We prefer 5-star hotels and have a flexible budget.
        
        Note: If you don't specify dates, we'll plan for a one-week trip starting 10 days from now.
        """
        
        st.session_state.travel_details['natural_input'] = st.text_area(
            "Describe your ideal trip",
            placeholder=example_text,
            height=150,
            key="travel_input"
        )

    def parse_travel_details(self) -> Dict[str, Any]:
        """Parse natural language input using LLM"""
        if not st.session_state.travel_details['natural_input']:
            return None
            
        prompt = TRAVEL_PROMPT.format(
            user_input=st.session_state.travel_details['natural_input'],
            current_date=datetime.now().strftime('%Y-%m-%d')

        )
        
        try:
            # Get response from LLM
            response = self.llm.process(prompt)
            
            # Log raw response for debugging
            logger.info("Raw LLM Response:\n%s", response)
            
            # Clean the response
            cleaned_response = response.strip()
            if not cleaned_response:
                raise ValueError("Empty response from LLM")
                
            # Try to find JSON content if response contains other text
            if cleaned_response.find('{') != -1:
                json_start = cleaned_response.find('{')
                json_end = cleaned_response.rfind('}') + 1
                cleaned_response = cleaned_response[json_start:json_end]
            
            # Parse JSON
            parsed_details = json.loads(cleaned_response)
            
            # Validate required fields
            required_fields = ['origin', 'destination', 'travelers', 'duration_days']
            missing_fields = [field for field in required_fields if field not in parsed_details]
            if missing_fields:
                raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
            
            # Set default values for optional fields
            parsed_details.setdefault('budget_level', 'moderate')
            parsed_details.setdefault('hotel_preference', '4')
            parsed_details.setdefault('interests', '')
            parsed_details.setdefault('additional_notes', '')
            
            # Ensure travelers is properly formatted
            if not isinstance(parsed_details['travelers'], dict):
                parsed_details['travelers'] = {'adults': 2, 'children': 0}
            
            # Log parsed details
            logger.info("Parsed Travel Details:\n%s", 
                json.dumps(parsed_details, indent=2, ensure_ascii=False))
            
            return parsed_details
            
        except json.JSONDecodeError as e:
            st.error(f"""
            Failed to parse LLM response as JSON. 
            Error: {str(e)}
            Response: {response[:200]}...
            """)
            logger.error("JSON Parse Error - Full Response:\n%s", response)
            return None
            
        except Exception as e:
            st.error(f"Error processing travel details: {str(e)}")
            logger.error("Processing Error", exc_info=True)
            return None

    def display_parsed_details(self, parsed_details: Dict[str, Any]):
        """Display parsed travel details with all fields in a single form"""
        if not parsed_details:
            return

       # Ensure duration_days is set to 7 if it is None or not present
        if not parsed_details['duration_days']:
            duration_days = 7
        else:
            duration_days = parsed_details['duration_days']
        
         # Use existing dates from session state if available and not already set in parsed_details
        if parsed_details['dates']['departure']:
            departure_date = datetime.strptime(parsed_details['dates']['departure'], '%Y-%m-%d')
        elif not parsed_details['dates']['departure'] and 'departure_date' in st.session_state:
            departure_date = st.session_state.departure_date
        else:
            departure_date = datetime.now() + timedelta(days=10)

        if parsed_details['dates']['return']:
            return_date = datetime.strptime(parsed_details['dates']['return'], '%Y-%m-%d')
        elif not parsed_details['dates']['departure'] and 'return_date' in st.session_state:
            return_date = st.session_state.return_date
        else:
            return_date = departure_date +  timedelta(days=duration_days)

        st.write("### 🎯 Here's what I understood (Edit if needed)")
        
        # Create form for all details
        with st.form(key='edit_details_form'):
            # Date selection
            st.write("📅 **Travel Dates**")
            col1, col2 = st.columns(2)
            
            with col1:
                departure = st.date_input(
                    "Departure Date",
                    value=departure_date,
                    min_value=datetime.now(),
                    key='departure_date'
                )
            
            with col2:
                return_date = st.date_input(
                    "Return Date",
                    value=return_date,
                    min_value=departure,
                    key='return_date'
                )

            # Calculate duration
            duration = (return_date - departure).days
            st.info(f"🗓️ **Trip Duration:** {duration} days")

            # Rest of the form fields...
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # Location details...
                origin = st.text_input("From", value=parsed_details.get('origin', ''))
                destination = st.text_input("To", value=parsed_details.get('destination', ''))

            with col2:
                # Traveler details...
                adults = st.number_input("Adults", 1, 10, value=parsed_details.get('travelers', {}).get('adults', 2))
                children = st.number_input("Children", 0, 6, value=parsed_details.get('travelers', {}).get('children', 0))

            with col3:
                # Preferences...
                budget = st.selectbox("Budget Level", ['economy', 'moderate', 'luxury'], 
                                    index=['economy', 'moderate', 'luxury'].index(parsed_details.get('budget_level', 'moderate')))
                hotel = st.selectbox("Hotel Preference (⭐)", ['3', '4', '5'],
                                   index=['3', '4', '5'].index(str(parsed_details.get('hotel_preference', '4'))))

            # Interests and Notes
            interests = st.text_area("Interests & Activities", value=parsed_details.get('interests', ''))
            notes = st.text_area("Additional Notes", value=parsed_details.get('additional_notes', ''))

            if st.form_submit_button("Confirm All Details ✅"):
                updated_details = {
                    'origin': origin.strip(),
                    'destination': destination.strip(),
                    'travelers': {
                        'adults': adults,
                        'children': children
                    },
                    'duration_days': duration,
                    'dates': {
                        'departure': departure.strftime('%Y-%m-%d'),
                        'return': return_date.strftime('%Y-%m-%d')
                    },
                    'budget_level': budget,
                    'hotel_preference': hotel,
                    'interests': interests.strip(),
                    'additional_notes': notes.strip()
                }
                
                # Update session state
                st.session_state.travel_details.update({
                    'parsed_details': updated_details,
                    'dates': updated_details['dates'],
                    'duration_days': duration
                })
                
                # Log the output
                logger.info("\nConfirmed Travel Details:\n%s", 
                    json.dumps(updated_details, indent=2, ensure_ascii=False))
                
                # Show success message
                st.success(f"""
                ✅ Trip details confirmed successfully!
                • {origin} → {destination}
                • {duration} days ({departure.strftime('%B %d')} - {return_date.strftime('%B %d, %Y')})
                • {adults} adults, {children} children
                • Budget: {budget.title()}
                • Hotel: {hotel}⭐
                """)
                
                return updated_details

        return parsed_details

    def process_and_display(self):
        """Process input and display results"""
        if st.button("Plan My Trip 🚀", type="primary"):
            if not st.session_state.travel_details['natural_input']:
                st.warning("Please describe your trip first!")
                return

            with st.spinner("Analyzing your travel preferences..."):
                parsed_details = self.parse_travel_details()
                if parsed_details:
                    updated_details = self.display_parsed_details(parsed_details)
                    if updated_details:
                        st.session_state.travel_details['parsed_details'] = updated_details

    def run(self):
        """Main application flow"""
        self.render_header()
        self.render_natural_input()
        self.process_and_display()

    def update_return_date(self):
        """Update return date when departure date changes"""
        if 'departure_date' in st.session_state and 'return_date' in st.session_state:
            departure = st.session_state.departure_date
            current_return = st.session_state.return_date
            
            # Keep the same duration when departure changes
            current_duration = (current_return - departure).days
            new_return = departure + timedelta(days=current_duration)
            
            # Update return date
            st.session_state.return_date = new_return
            
            # Update session state
            st.session_state.travel_details['dates'] = {
                'departure': departure.strftime('%Y-%m-%d'),
                'return': new_return.strftime('%Y-%m-%d')
            }

    def update_duration(self):
        """Update duration when either date changes"""
        if 'departure_date' in st.session_state and 'return_date' in st.session_state:
            departure = st.session_state.departure_date
            return_date = st.session_state.return_date
            
            # Calculate new duration
            duration = (return_date - departure).days
            
            # Update session state
            st.session_state.travel_details.update({
                'duration_days': duration,
                'dates': {
                    'departure': departure.strftime('%Y-%m-%d'),
                    'return': return_date.strftime('%Y-%m-%d')
                }
            })
            
            # Force rerun to update UI
            st.experimental_rerun()

if __name__ == "__main__":
    st.set_page_config(
        page_title="AI Travel Planner",
        page_icon="✈️",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    app = ModernTravelPlannerApp()
    app.run()
