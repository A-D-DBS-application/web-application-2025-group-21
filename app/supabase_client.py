import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from supabase import create_client, Client  # Import the official client

DATABASE_URL = os.getenv("DATABASE_URL")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set.")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL or SUPABASE_KEY is not set in .env")

# 1. SQLAlchemy Engine (for Database)
engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

def get_session():
    return SessionLocal()

# 2. Supabase Client (for Storage/Auth/Realtime)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)