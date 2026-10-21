import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    demo_mode: bool = str(os.getenv("DEMO_MODE", "true")).lower() == "true"
    gmail_credentials_path: str = os.getenv("GMAIL_CREDENTIALS_PATH", "credentials.json")
    gmail_token_path: str = os.getenv("GMAIL_TOKEN_PATH", "token.json")
    model_provider: str = os.getenv("MODEL_PROVIDER", "openai")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    twilio_account_sid: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    twilio_auth_token: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    twilio_from: str = os.getenv("TWILIO_FROM", "")
    twilio_to: str = os.getenv("TWILIO_TO", "")


settings = Settings()
