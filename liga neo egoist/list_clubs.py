from app import create_app
from models import db, Club

app = create_app()
with app.app_context():
    clubs = Club.query.filter_by(active=True).order_by(Club.name).all()
    for c in clubs:
        logo = "SIM" if c.logo_url else "NAO"
        country = c.country.name if c.country else "?"
        print(f"{c.short_name:5} | {c.name:20} | {country:12} | logo: {logo}")
