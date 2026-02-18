from pydantic_settings import BaseSettings
from pydantic import AnyUrl
from typing import Optional


class Setttings(BaseSettings):
    OPENAI_API_KEY: str

    class Config:
        env_file = ".env"  # Load values from .env file


settings = Setttings()