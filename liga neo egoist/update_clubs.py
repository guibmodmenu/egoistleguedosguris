from app import create_app
from models import db, Country, Club

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
    ]:
        c = Country(name=name, code=code, flag=flag)
        db.session.add(c)
        db.session.flush()
        countries[code] = c

    clubs_data = [
        # ESPANHA
        ('ESP', 'FC Barcha',      'BAR', '#A50044', '#004D98', 'Camp Nou', 'Time do Lavinho. Futebol criativo e livre.'),
        ('ESP', 'Real Madrid',    'RMA', '#FEBE10', '#00529F', 'Bernabeu', 'O maior clube da Espanha.'),
        ('ESP', 'Atletico Madrid','ATM', '#CB3524', '#272E61', 'Metropolitano', 'Time forte e fisico.'),
        ('ESP', 'Sevilla FC',     'SEV', '#D4001E', '#FFFFFF', 'Sanchez Pizjuan', 'Historico da Espanha.'),

        # FRANCA
        ('FRA', 'Paris X Gen',    'PSX', '#004170', '#DA291C', 'Parc des Princes', 'Time do Charles Chevalier. Ataque agressivo.'),
        ('FRA', 'AS Monaco',      'MON', '#E2001A', '#FFFFFF', 'Louis II', 'Jovens talentosos.'),
        ('FRA', 'Olympique Lyon', 'LYO', '#2FAEE0', '#1A2E5A', 'Groupama Stadium', 'Tradicao francesa.'),
        ('FRA', 'Olympique Marseille', 'MAR', '#2FAEE0', '#FFFFFF', 'Velodrome', 'Paixao do sul da Franca.'),

        # ITALIA
        ('ITA', 'Ubers',          'UBR', '#000000', '#FFFFFF', 'Allianz Stadium', 'Time do Marc Snuffy. Tatica defensiva.'),
        ('ITA', 'AC Milan',       'MIL', '#FB090B', '#000000', 'San Siro', 'Historico italiano.'),
        ('ITA', 'Inter Milan',    'INT', '#0068A8', '#000000', 'San Siro', 'Rivalidade milanesa.'),
        ('ITA', 'AS Roma',        'ROM', '#8E1F2F', '#F0BC42', 'Olimpico', 'Roma eterna.'),

        # INGLATERRA
        ('ENG', 'Manshine City',  'MCI', '#6CABDD', '#1C2C5B', 'Etihad Stadium', 'Time do Chris Prince. Velocidade e fisico.'),
        ('ENG', 'Manchester FC',  'MAN', '#DA291C', '#FBE122', 'Old Trafford', 'Forca inglesa.'),
        ('ENG', 'Liverpool FC',   'LIV', '#C8102E', '#00B2A9', 'Anfield', 'Anfield e seus famosos critically.'),
        ('ENG', 'Chelsea FC',     'CHE', '#034694', '#DBA111', 'Stamford Bridge', 'Londres azul.'),
    ]

    for country_code, name, short, primary, secondary, stadium, desc in clubs_data:
        c = Club(
            country_id=countries[country_code].id,
            name=name, short_name=short,
            primary_color=primary, secondary_color=secondary,
            stadium=stadium, max_players=18,
        )
        db.session.add(c)

    db.session.commit()
    print("Clubes atualizados com nomes do Blue Lock NEL!")
    print("")
    print("INGLATERRA:")
    print("  Manshine City (NEL) - Chris Prince")
    print("  Manchester FC")
    print("  Liverpool FC")
    print("  Chelsea FC")
    print("")
    print("ESPANHA:")
    print("  FC Barcha (NEL) - Lavinho")
    print("  Real Madrid")
    print("  Atletico Madrid")
    print("  Sevilla FC")
    print("")
    print("ITALIA:")
    print("  Ubers (NEL) - Marc Snuffy")
    print("  AC Milan")
    print("  Inter Milan")
    print("  AS Roma")
    print("")
    print("FRANCA:")
    print("  Paris X Gen (NEL) - Charles Chevalier")
    print("  AS Monaco")
    print("  Olympique Lyon")
    print("  Olympique Marseille")
