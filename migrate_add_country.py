"""
Migration: Add 'country' column to proxy table.
Run once: python migrate_add_country.py
"""
from app.config.config import Config
from sqlalchemy import create_engine, text

db_url = (
    f"mysql+mysqlconnector://{Config.database_user}:{Config.database_pass}"
    f"@{Config.database_host}:{Config.database_port}/{Config.database_name}"
)
engine = create_engine(db_url)

with engine.connect() as conn:
    conn.execute(text("ALTER TABLE proxy ADD COLUMN country VARCHAR(2) NULL"))
    print("Done: added 'country' column to proxy table.")
