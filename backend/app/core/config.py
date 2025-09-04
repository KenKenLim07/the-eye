from pydantic import BaseModel
import os
from dotenv import load_dotenv, find_dotenv

# Load .env from project root or current dir
load_dotenv(find_dotenv(filename=".env", usecwd=True), override=False)

class Settings(BaseModel):
    api_prefix: str = "/api"
    env: str = os.getenv("ENV", "development")

    # Redis / Celery
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    celery_broker_url: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    celery_result_backend: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

    # Supabase
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_service_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

settings = Settings() 