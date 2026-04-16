import os

AI_PROVIDER = "openai"
MODEL = "gpt-4o-mini"
TEMPERATURE = 0.7
MAX_TOKENS = 4096

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

BSC_RPC_URL = os.getenv("RPC_URL")
MIN_REQUIRED_BNB = 0.5