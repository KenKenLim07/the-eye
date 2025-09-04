from supabase import create_client, Client
from .config import settings

_supabase: Client | None = None

def get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        if not settings.supabase_url or not settings.supabase_service_key:
            raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
        _supabase = create_client(settings.supabase_url, settings.supabase_service_key)
    return _supabase 