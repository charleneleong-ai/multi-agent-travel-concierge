import requests
from PIL import Image
from transformers import AutoModelForCausalLM, AutoProcessor, AutoTokenizer, AutoModelForTokenClassification,pipeline
from langchain.agents import initialize_agent, AgentType, Tool
from langchain.prompts import PromptTemplate
from together import Together


ner_extractor_model_tokenizer = AutoTokenizer.from_pretrained("ml6team/bert-base-uncased-city-country-ner")

ner_extractor_model = AutoModelForTokenClassification.from_pretrained("ml6team/bert-base-uncased-city-country-ner")


class WeatherRetriever:
    def __init__(self, api_key):
        self.api_key = api_key

    def get_weather(self, location):
        weather_url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&appid={self.api_key}&units=metric"
        response = requests.get(weather_url)
        data = response.json()
        if data.get("main"):
            temperature = data["main"]["temp"]
            description = data["weather"][0]["description"]
            return {"temperature": temperature, "description": description}
        else:
            return None

class DeepSeekLLM:
    def __init__(self, api_key):
        self.client = Together(api_key=api_key)

    def call_deepseek(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model="deepseek-ai/deepseek-llm-67b-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            temperature=0.7,
            top_p=0.7,
            top_k=50,
            repetition_penalty=1,
            stop=["<｜begin▁of▁sentence｜>", "<｜end▁of▁sentence｜>"],
            stream=False
        )
        if response.choices:
            return response.choices[0].message.content
        else:
            return "No response received."

class TravelAssistant:
    def __init__(self, deepseek_api_key, weather_api_key):
        self.llm = DeepSeekLLM(api_key=deepseek_api_key)
        self.weather_retriever = WeatherRetriever(api_key=weather_api_key)

    def get_weather_for_location(self, location):
        weather_data = self.weather_retriever.get_weather(location)
        if weather_data:
            return f"The weather in {location} is {weather_data['description']} with a temperature of {weather_data['temperature']}°C."
        else:
            return f"Weather data could not be retrieved for {location}."

    def suggest_items_for_travel(self, location, weather):
        prompt = f"What items should I bring for traveling to {location} considering the weather: {weather}?"
        return self.llm.call_deepseek(prompt)

    def process_text_and_image(self, input_text, image_path):
        # Extract location and get weather information
        location = self.extract_location(input_text)
        weather_info = self.get_weather_for_location(location)

        # Suggest items based on location and weather
        suggested_items = self.suggest_items_for_travel(location, weather_info)

        # Check items in the image
        image_items = self.extract_items_from_image(image_path)
        print("Items in the image:", image_items)

        # Identify missing items
        missing_items = self.compare_items(image_items, suggested_items)

        return {"location": location, "weather": weather_info, "suggested_items": suggested_items, "missing_items": missing_items}


    def extract_location(self, input_text):
        nlp = pipeline('ner', model=ner_extractor_model, tokenizer=ner_extractor_model_tokenizer, aggregation_strategy="simple")
        location_results = nlp(input_text)
        return location_results[0]['word']


    def extract_items_from_image(self, image_path):
        model_id = "microsoft/Phi-3.5-vision-instruct"
        model = AutoModelForCausalLM.from_pretrained(model_id, device_map="cuda", trust_remote_code=True, torch_dtype="auto", _attn_implementation='eager')
        processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True, num_crops=4)

        image = Image.open(image_path)
        messages = [{"role": "user", "content": "List the items in the image in terms of their purpose for travel.<|image_1|>"}]

        prompt = processor.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = processor(prompt, [image], return_tensors="pt").to("cuda:0")

        generation_args = {"max_new_tokens": 1000, "temperature": 0.0, "do_sample": False}
        generate_ids = model.generate(**inputs, eos_token_id=processor.tokenizer.eos_token_id, **generation_args)
        generate_ids = generate_ids[:, inputs['input_ids'].shape[1]:]

        response = processor.batch_decode(generate_ids, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0]
        return response

    def compare_items(self, image_items, suggested_items):
        missing_items = set(suggested_items.split(", ")) - set(image_items.split(", "))
        return missing_items