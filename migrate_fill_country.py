"""
Fill 'country' column for existing proxies that have country=NULL.
Run once: python migrate_fill_country.py
"""
from app.config.config import Config
from app.util.GeoIP import get_country
from sqlalchemy import create_engine, text

db_url = (
    f"mysql+mysqlconnector://{Config.database_user}:{Config.database_pass}"
    f"@{Config.database_host}:{Config.database_port}/{Config.database_name}"
)
engine = create_engine(db_url)

with engine.connect() as conn:
    rows = conn.execute(text("SELECT id, server FROM proxy WHERE country IS NULL")).fetchall()
    print(f"Found {len(rows)} proxies without country.")
    updated = 0
    for row in rows:
        country = get_country(row.server)
        if country:
            conn.execute(text("UPDATE proxy SET country = :country WHERE id = :id"), {"country": country, "id": row.id})
            updated += 1
        print(f"  [{updated}/{len(rows)}] {row.server} -> {country}")
    print(f"Done: updated {updated} out of {len(rows)} proxies.")
