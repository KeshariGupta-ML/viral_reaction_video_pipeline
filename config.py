import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Determine project root directory
BASE_DIR = Path(__file__).resolve().parent

# Explicitly load environment variables from .env file into os.environ
load_dotenv(dotenv_path=BASE_DIR / ".env")

class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    # LLM Settings (Google Gemini via LangChain)
    # Pydantic will now automatically find it since load_dotenv() injected it into os.environ
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY")
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # Server Settings
    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = 8000
    DEBUG: bool = True

    # Directories
    STORAGE_DIR: Path = BASE_DIR / "storage"
    TEMP_DIR: Path = BASE_DIR / "storage" / "temp"
    OUTPUT_DIR: Path = BASE_DIR / "storage" / "output"
    STATIC_DIR: Path = BASE_DIR / "app" / "static"
    TEMPLATES_DIR: Path = BASE_DIR / "app" / "templates"
    VIDEOS_DIR: Path = STORAGE_DIR / "videos"
    MEMES_DIR: Path = BASE_DIR / "assets" / "memes"

settings = Settings()

# Ensure required runtime directories exist
settings.TEMP_DIR.mkdir(parents=True, exist_ok=True)
settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)