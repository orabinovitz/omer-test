"""Configuration module to handle environment variables."""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings:
    """Application settings loaded from environment variables."""
    
    # API Keys
    PERPLEXITY_API_KEY = os.getenv("DYNACONF_PERPLEXITY_API_KEY")
    OPENAI_API_KEY = os.getenv("DYNACONF_OPENAI_API_KEY")
    APIFY_API_KEY = os.getenv("DYNACONF_APIFY_API_KEY")
    ATLASSIAN_API_KEY = os.getenv("DYNACONF_ATLASSIAN_API_KEY")
    FIGMA_API_KEY = os.getenv("DYNACONF_FIGMA_API_KEY")
    APPFOLLOW_API_KEY = os.getenv("DYNACONF_APPFOLLOW_API_KEY")
    ANTHROPIC_API_KEY = os.getenv("DYNACONF_ANTHROPIC_API_KEY")
    FAL_API_TOKEN = os.getenv("DYNACONF_FAL_API_TOKEN")
    X_API_KEY = os.getenv("DYNACONF_X_API_KEY")
    X_API_SECRET = os.getenv("DYNACONF_X_API_SECRET")
    X_BEARER_TOKEN = os.getenv("DYNACONF_X_BEARER_TOKEN")
    APOLLO_API_KEY = os.getenv("DYNACONF_APOLLO_API_KEY")
    GEMINI_API_KEY = os.getenv("DYNACONF_GEMINI_API_KEY")
    RUNWAY_API_KEY = os.getenv("DYNACONF_RUNWAY_API_KEY")
    REPLICATE_API_KEY = os.getenv("DYNACONF_REPLICATE_API_KEY")
    SERPAPI_KEY = os.getenv("DYNACONF_SERPAPI_KEY")
    
    # Google Drive Service Account Credentials
    DRIVE_SA_CREDENTIALS = os.getenv("DYNACONF_DRIVE_SA_CREDENTIALS")

# Create settings instance
settings = Settings() 