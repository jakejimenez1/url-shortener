from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://urlshortener:secretpassword@localhost:5432/urls")

## SQLite fallback for local development
if not DATABASE_URL.startswith("postgresql"):
    DATABASE_URL = "sqlite:///./url_shortener.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

## create a database session to write or query to the DB
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

## initialize database tables
def init_db():
    from models import URL, Click
    Base.metadata.create_all(bind=engine)
