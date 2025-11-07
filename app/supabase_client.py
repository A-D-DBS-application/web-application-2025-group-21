import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base  # zorg dat Base in models.py staat

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError('DATABASE_URL not set. Gebruik: setx DATABASE_URL "postgresql://postgres:WACHTWOORD@db.yezkgrihchdjhiypfykc.supabase.co:5432/postgres"')

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

def get_session():
    return SessionLocal()


# Maak tabellen aan (indien niet aanwezig)
#dit niet zeker denk dat we al tabellen hadden
#try:
    #Base.metadata.create_all(engine)
#except Exception as e:
    #print("⚠️ Kon tabellen niet automatisch maken:", e)

#als nog niet hebben moeten we dit invoeren in terminal als we willen runnen
#python
#>>> from app.supabase_client import engine
#>>> result = engine.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
#>>> for row in result: print(row)

#dit is voor database te linken in terminal en hierna sluiten en trg laden maar vergeet niet alles aan te passen
#setx DATABASE_URL "postgresql://postgres:password@localhost:5432/yourdb"

#venv act: .\venv\Scripts\Activate.ps1

#app starten: python run.py



