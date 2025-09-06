# llm/config.py
import os

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
DEFAULT_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
TEMPERATURE = float(os.getenv('OPENAI_TEMPERATURE', '0.2'))
