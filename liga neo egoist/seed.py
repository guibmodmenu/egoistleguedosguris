import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from models import db, Country, Club, Season, SeasonClub, User, Player
from werkzeug.security import generate_password_hash


def seed():
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()

        countries = {}
        for name, code, flag in [
            ('Espanha', 'ESP', '\U0001f1ea\U0001f1f8'),
            ('Franca', 'FRA', '\U0001f1eb\U0001f1f7'),
            ('Italia', 'ITA', '\U0001f1ee\U0001f1f9'),
            ('Inglaterra', 'ENG', '\U0001f3f4\U000e0067\U000e0062\U000e0065\U000e006e\U000e0067\U000e007f'),
            ('Alemanha', 'GER', '\U0001f1e9\U0001f1ea'),
        ]:
            c = Country(name=name, code=code, flag=flag)
            db.session.add(c)
            db.session.flush()
            countries[code] = c

        clubs_data = [
            # ESPANHA
            ('ESP', 'FC Barcha', 'BAR', '#A50044', '#004D98', 'Camp Nou'),
            ('ESP', 'Real Madrid', 'RMA', '#FEBE10', '#00529F', 'Bernabeu'),
            ('ESP', 'Atletico Madrid', 'ATM', '#CB3524', '#272E61', 'Metropolitano'),
            ('ESP', 'Sevilla FC', 'SEV', '#D4001E', '#FFFFFF', 'Sanchez Pizjuan'),
            # FRANCA
            ('FRA', 'Paris X Gen', 'PSX', '#004170', '#DA291C', 'Parc des Princes'),
            ('FRA', 'AS Monaco', 'MON', '#E2001A', '#FFFFFF', 'Louis II'),
            ('FRA', 'Olympique Lyon', 'LYO', '#2FAEE0', '#1A2E5A', 'Groupama Stadium'),
            ('FRA', 'Olympique Marseille', 'MAR', '#2FAEE0', '#FFFFFF', 'Velodrome'),
            # ITALIA
            ('ITA', 'Ubers', 'UBR', '#000000', '#FFFFFF', 'Allianz Stadium'),
            ('ITA', 'AC Milan', 'MIL', '#FB090B', '#000000', 'San Siro'),
            ('ITA', 'Inter Milan', 'INT', '#0068A8', '#000000', 'San Siro'),
            ('ITA', 'AS Roma', 'ROM', '#8E1F2F', '#F0BC42', 'Olimpico'),
            # INGLATERRA
            ('ENG', 'Manshine City', 'MCI', '#6CABDD', '#1C2C5B', 'Etihad Stadium'),
            ('ENG', 'Manchester FC', 'MAN', '#DA291C', '#FBE122', 'Old Trafford'),
            ('ENG', 'Liverpool FC', 'LIV', '#C8102E', '#00B2A9', 'Anfield'),
            ('ENG', 'Chelsea FC', 'CHE', '#034694', '#DBA111', 'Stamford Bridge'),
            # ALEMANHA
            ('GER', 'Bastard Munchen', 'BMW', '#000000', '#FFFFFF', 'Allianz Arena'),
            ('GER', 'Bayern Munchen', 'BAY', '#DC052D', '#0066B2', 'Allianz Arena'),
            ('GER', 'Borussia Dortmund', 'BVB', '#FDE100', '#000000', 'Signal Iduna Park'),
            ('GER', 'RB Leipzig', 'RBL', '#DD0741', '#00163E', 'Red Bull Arena'),
        ]
        clubs = {}
        for country_code, name, short, primary, secondary, stadium in clubs_data:
            c = Club(
                country_id=countries[country_code].id,
                name=name, short_name=short,
                primary_color=primary, secondary_color=secondary,
                stadium=stadium
            )
            db.session.add(c)
            db.session.flush()
            clubs[short] = c

        now = datetime.now(timezone.utc)
        season = Season(
            name='Season 01',
            description='Neo Egoist League - Blue Lock',
            start_date=now - timedelta(days=30),
            end_date=now + timedelta(days=150),
            status='ACTIVE',
            initial_market_value=50000000,
        )
        db.session.add(season)
        db.session.flush()

        for short, pts, w, d, l, gf, ga in [
            ('RMA', 0, 0, 0, 0, 0, 0),
            ('PSX', 0, 0, 0, 0, 0, 0),
            ('BAR', 0, 0, 0, 0, 0, 0),
            ('MCI', 0, 0, 0, 0, 0, 0),
            ('MIL', 0, 0, 0, 0, 0, 0),
            ('INT', 0, 0, 0, 0, 0, 0),
            ('LIV', 0, 0, 0, 0, 0, 0),
            ('UBR', 0, 0, 0, 0, 0, 0),
            ('ATM', 0, 0, 0, 0, 0, 0),
            ('CHE', 0, 0, 0, 0, 0, 0),
            ('MON', 0, 0, 0, 0, 0, 0),
            ('ROM', 0, 0, 0, 0, 0, 0),
            ('LYO', 0, 0, 0, 0, 0, 0),
            ('SEV', 0, 0, 0, 0, 0, 0),
            ('MAN', 0, 0, 0, 0, 0, 0),
            ('MAR', 0, 0, 0, 0, 0, 0),
            ('BMW', 0, 0, 0, 0, 0, 0),
            ('BAY', 0, 0, 0, 0, 0, 0),
            ('BVB', 0, 0, 0, 0, 0, 0),
            ('RBL', 0, 0, 0, 0, 0, 0),
        ]:
            sc = SeasonClub(
                season_id=season.id, club_id=clubs[short].id,
                points=pts, wins=w, draws=d, losses=l,
                goals_for=gf, goals_against=ga
            )
            db.session.add(sc)

        admin_user = User(
            username='admin',
            password_hash=generate_password_hash('admin123'),
            role='ADMIN',
            status='ACTIVE'
        )
        db.session.add(admin_user)
        db.session.flush()

        admin_player = Player(
            user_id=admin_user.id,
            nickname='Admin',
            display_name='Administrador',
            icon_key='shield',
            position='MIDFIELDER',
            country_code='BRA',
        )
        db.session.add(admin_player)

        db.session.commit()
        print("Seed concluido!")
        print("Admin: admin / admin123")
        print("Nenhum jogador de exemplo - todos devem se registrar via convite.")


if __name__ == '__main__':
    seed()
