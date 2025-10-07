import logging
import os
from dotenv import load_dotenv

import google.generativeai as genai # <-- Required for the model existence check
from langchain_google_genai import ChatGoogleGenerativeAI
# Load environment variables from .env file
load_dotenv()

# This line configures the 'google.generativeai' library so it can call list_models().
# It reads the API key that was already loaded by dotenv in main_agent.py.
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# A reliable default model to fall back to
DEFAULT_MODEL = "gemini-2.5-flash"
_SUPPORTED_MODELS = None

def _get_supported_models():
    global _SUPPORTED_MODELS
    if _SUPPORTED_MODELS is None:
        logging.info("Fetching the list of available models from Google AI...")
        _SUPPORTED_MODELS = [
            model.name.replace('models/', '')
            for model in genai.list_models()
            if 'generateContent' in model.supported_generation_methods
        ]
    return _SUPPORTED_MODELS

def get_llm(model_name: str, **kwargs) -> ChatGoogleGenerativeAI:
    supported_models = _get_supported_models()
    if model_name in supported_models:
        logging.info(f"Model '{model_name}' is supported. Initializing...")
        return ChatGoogleGenerativeAI(model=model_name, **kwargs)
    else:
        logging.warning(
            f"Model '{model_name}' not found. Falling back to default '{DEFAULT_MODEL}'."
        )
        return ChatGoogleGenerativeAI(model=DEFAULT_MODEL, **kwargs)
