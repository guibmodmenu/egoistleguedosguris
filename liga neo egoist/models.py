from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
DEFAULT_INITIAL_MARKET_VALUE = 10_000_000
LEGACY_INITIAL_MARKET_VALUE = 50_000_000


def utcnow():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(40), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(16), nullable=False, default='USER')
    status = db.Column(db.String(16), nullable=False, default='ACTIVE')
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    player = db.relationship('Player', backref='user', uselist=False, lazy=True)


class Player(db.Model):
    __tablename__ = 'players'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    nickname = db.Column(db.String(40), nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    avatar_url = db.Column(db.String(512))
    icon_key = db.Column(db.String(32), nullable=False, default='zap')
    country_code = db.Column(db.String(3), default='ESP')
    position = db.Column(db.String(16), nullable=False, default='FORWARD')
    number = db.Column(db.Integer, default=10)
    bio = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)


class Country(db.Model):
    __tablename__ = 'countries'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    code = db.Column(db.String(3), unique=True, nullable=False)
    flag = db.Column(db.String(8))

    clubs = db.relationship('Club', backref='country', lazy=True)


class Club(db.Model):
    __tablename__ = 'clubs'

    id = db.Column(db.Integer, primary_key=True)
    country_id = db.Column(db.Integer, db.ForeignKey('countries.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    short_name = db.Column(db.String(16), nullable=False)
    logo_url = db.Column(db.String(512))
    primary_color = db.Column(db.String(16))
    secondary_color = db.Column(db.String(16))
    stadium = db.Column(db.String(120))
    max_players = db.Column(db.Integer, nullable=False, default=18)
    active = db.Column(db.Boolean, nullable=False, default=True)

    home_matches = db.relationship('Match', foreign_keys='Match.home_club_id', backref='home_club', lazy=True)
    away_matches = db.relationship('Match', foreign_keys='Match.away_club_id', backref='away_club', lazy=True)


class Season(db.Model):
    __tablename__ = 'seasons'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text)
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)
    status = db.Column(db.String(16), nullable=False, default='UPCOMING')
    initial_market_value = db.Column(db.BigInteger, nullable=False, default=DEFAULT_INITIAL_MARKET_VALUE)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)


class SeasonClub(db.Model):
    __tablename__ = 'season_clubs'

    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey('seasons.id'), nullable=False)
    club_id = db.Column(db.Integer, db.ForeignKey('clubs.id'), nullable=False)
    points = db.Column(db.Integer, nullable=False, default=0)
    wins = db.Column(db.Integer, nullable=False, default=0)
    draws = db.Column(db.Integer, nullable=False, default=0)
    losses = db.Column(db.Integer, nullable=False, default=0)
    goals_for = db.Column(db.Integer, nullable=False, default=0)
    goals_against = db.Column(db.Integer, nullable=False, default=0)
    position = db.Column(db.Integer)

    season = db.relationship('Season', backref='clubs')
    club = db.relationship('Club', backref='season_clubs')

    __table_args__ = (db.UniqueConstraint('season_id', 'club_id'),)


class SeasonPlayer(db.Model):
    __tablename__ = 'season_players'

    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey('seasons.id'), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False)
    club_id = db.Column(db.Integer, db.ForeignKey('clubs.id'), nullable=False)
    starting_market_value = db.Column(db.BigInteger, nullable=False)
    current_market_value = db.Column(db.BigInteger, nullable=False)
    overall = db.Column(db.Float, nullable=False, default=70)
    matches = db.Column(db.Integer, nullable=False, default=0)
    wins = db.Column(db.Integer, nullable=False, default=0)
    draws = db.Column(db.Integer, nullable=False, default=0)
    losses = db.Column(db.Integer, nullable=False, default=0)
    goals = db.Column(db.Integer, nullable=False, default=0)
    assists = db.Column(db.Integer, nullable=False, default=0)
    rating_average = db.Column(db.Float, nullable=False, default=0)
    mvp_count = db.Column(db.Integer, nullable=False, default=0)
    rank = db.Column(db.Integer)

    season = db.relationship('Season', backref='players')
    player = db.relationship('Player', backref='season_players')
    club = db.relationship('Club', backref='season_players')

    __table_args__ = (db.UniqueConstraint('season_id', 'player_id'),)


class SeasonPlayerAttributes(db.Model):
    __tablename__ = 'season_player_attributes'

    id = db.Column(db.Integer, primary_key=True)
    season_player_id = db.Column(
        db.Integer, db.ForeignKey('season_players.id'), nullable=False, unique=True
    )
    defense = db.Column(db.Integer, nullable=False, default=50)
    passing = db.Column(db.Integer, nullable=False, default=50)
    physical = db.Column(db.Integer, nullable=False, default=50)
    speed = db.Column(db.Integer, nullable=False, default=50)
    attack = db.Column(db.Integer, nullable=False, default=50)

    season_player = db.relationship(
        'SeasonPlayer', backref=db.backref('attributes', uselist=False)
    )

    __table_args__ = (
        db.CheckConstraint('defense BETWEEN 0 AND 100', name='ck_player_attributes_defense'),
        db.CheckConstraint('passing BETWEEN 0 AND 100', name='ck_player_attributes_passing'),
        db.CheckConstraint('physical BETWEEN 0 AND 100', name='ck_player_attributes_physical'),
        db.CheckConstraint('speed BETWEEN 0 AND 100', name='ck_player_attributes_speed'),
        db.CheckConstraint('attack BETWEEN 0 AND 100', name='ck_player_attributes_attack'),
    )


class Match(db.Model):
    __tablename__ = 'matches'

    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey('seasons.id'), nullable=False)
    home_club_id = db.Column(db.Integer, db.ForeignKey('clubs.id'), nullable=False)
    away_club_id = db.Column(db.Integer, db.ForeignKey('clubs.id'), nullable=False)
    home_score = db.Column(db.Integer, nullable=False, default=0)
    away_score = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(16), nullable=False, default='SCHEDULED')
    scheduled_at = db.Column(db.DateTime)
    processed_at = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    season = db.relationship('Season', backref='matches')
    players = db.relationship('MatchPlayer', backref='match', lazy=True)


class MatchPlayer(db.Model):
    __tablename__ = 'match_players'

    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey('matches.id'), nullable=False)
    season_player_id = db.Column(db.Integer, db.ForeignKey('season_players.id'), nullable=False)
    minutes = db.Column(db.Integer, nullable=False, default=0)
    goals = db.Column(db.Integer, nullable=False, default=0)
    assists = db.Column(db.Integer, nullable=False, default=0)
    shots = db.Column(db.Integer, nullable=False, default=0)
    shots_on_target = db.Column(db.Integer, nullable=False, default=0)
    passes = db.Column(db.Integer, nullable=False, default=0)
    accurate_passes = db.Column(db.Integer, nullable=False, default=0)
    chances_created = db.Column(db.Integer, nullable=False, default=0)
    tackles = db.Column(db.Integer, nullable=False, default=0)
    interceptions = db.Column(db.Integer, nullable=False, default=0)
    clearances = db.Column(db.Integer, nullable=False, default=0)
    blocks = db.Column(db.Integer, nullable=False, default=0)
    saves = db.Column(db.Integer, nullable=False, default=0)
    goals_conceded = db.Column(db.Integer, nullable=False, default=0)
    yellow_cards = db.Column(db.Integer, nullable=False, default=0)
    red_cards = db.Column(db.Integer, nullable=False, default=0)
    clean_sheet = db.Column(db.Boolean, nullable=False, default=False)
    rating = db.Column(db.Float, nullable=False, default=0)
    mvp = db.Column(db.Boolean, nullable=False, default=False)
    notes = db.Column(db.Text)

    season_player = db.relationship('SeasonPlayer', backref='match_players')

    __table_args__ = (db.UniqueConstraint('match_id', 'season_player_id'),)


class Invite(db.Model):
    __tablename__ = 'invites'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, nullable=False)
    max_uses = db.Column(db.Integer, nullable=False, default=1)
    uses = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(16), nullable=False, default='ACTIVE')
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'))
    valid_until = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    creator = db.relationship('User', backref='created_invites')
    player = db.relationship('Player', backref='invites')


class PlayerValueHistory(db.Model):
    __tablename__ = 'player_value_history'

    id = db.Column(db.Integer, primary_key=True)
    season_player_id = db.Column(db.Integer, db.ForeignKey('season_players.id'), nullable=False)
    match_id = db.Column(db.Integer, db.ForeignKey('matches.id'))
    previous_value = db.Column(db.BigInteger, nullable=False)
    change = db.Column(db.BigInteger, nullable=False)
    change_percent = db.Column(db.Float, nullable=False)
    new_value = db.Column(db.BigInteger, nullable=False)
    reason = db.Column(db.Text)
    source = db.Column(db.String(16), nullable=False, default='SYSTEM')
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    season_player = db.relationship('SeasonPlayer', backref='value_history')
    match = db.relationship('Match', backref='value_history')


class MarketValueAnalysis(db.Model):
    __tablename__ = 'market_value_analysis'

    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey('matches.id'), nullable=False)
    season_player_id = db.Column(db.Integer, db.ForeignKey('season_players.id'), nullable=False)
    performance_score = db.Column(db.Float, nullable=False)
    market_value_change_percent = db.Column(db.Float, nullable=False)
    market_value_change = db.Column(db.BigInteger, nullable=False)
    confidence = db.Column(db.Float, nullable=False)
    reasoning = db.Column(db.Text)
    review_status = db.Column(db.String(16), nullable=False, default='PENDING')
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    match = db.relationship('Match', backref='ai_analyses')


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(64), nullable=False)
    target_type = db.Column(db.String(32))
    target_id = db.Column(db.Integer)
    old_value = db.Column(db.Text)
    new_value = db.Column(db.Text)
    reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    admin = db.relationship('User', backref='audit_logs')
