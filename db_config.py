"""
Central PostgreSQL connection settings (used by notebooks and app.py).

Edit the defaults below OR set environment variables before running:
    export PG_USER=postgres PG_PASSWORD=yourpass PG_HOST=localhost PG_PORT=5432 PG_DB=tmdb
The database must exist first -> in pgAdmin: right-click Databases > Create > Database > name "tmdb".
"""
import os
from sqlalchemy import create_engine

PG_USER = os.getenv("PG_USER", "kamila")
PG_PASSWORD = os.getenv("PG_PASSWORD")
if PG_PASSWORD is None:
    try:
        from local_secrets import PG_PASSWORD   # your real password lives here (git-ignored)
    except ImportError:
        PG_PASSWORD = "your_password"           # <-- or set env var PG_PASSWORD   
PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_DB = os.getenv("PG_DB", "tmdb")

DB_URL = f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"


def get_engine():
    """Return a SQLAlchemy engine connected to the tmdb PostgreSQL database."""
    return create_engine(DB_URL, pool_pre_ping=True)
