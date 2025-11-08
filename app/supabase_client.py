import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base  # zorg dat Base in models.py staat

# ✅ 1. Eerst .env inladen
load_dotenv()

# ✅ 2. Dan variabele ophalen
print("DEBUG: DATABASE_URL =", os.getenv("DATABASE_URL"))

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError('DATABASE_URL not set. Gebruik: setx DATABASE_URL "postgresql://postgres:WACHTWOORD@db.yezkgrihchdjhiypfykc.supabase.co:5432/postgres"')

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

def get_session():
    return SessionLocal()






