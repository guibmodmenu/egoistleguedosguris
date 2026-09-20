import os
import secrets

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Database: PostgreSQL in production, SQLite locally
DATABASE_URI = os.environ.get('DATABASE_URL')
if not DATABASE_URI:
    DATABASE_PATH = os.path.join(BASE_DIR, 'database', 'league.db')
    DATABASE_URI = f'sqlite:///{DATABASE_PATH}'

# Fix Render PostgreSQL URI (postgres:// -> postgresql://)
if DATABASE_URI and DATABASE_URI.startswith('postgres://'):
    DATABASE_URI = DATABASE_URI.replace('postgres://', 'postgresql://', 1)

# Secret key
_secret = os.environ.get('SECRET_KEY')
if not _secret:
    _keyfile = os.path.join(BASE_DIR, '.secret_key')
    if os.path.exists(_keyfile):
        with open(_keyfile, 'r') as f:
            _secret = f.read().strip()
    if not _secret:
        _secret = secrets.token_hex(32)
        with open(_keyfile, 'w') as f:
            f.write(_secret)

SECRET_KEY = _secret

MAX_MARKET_INCREASE = int(os.environ.get('MAX_MARKET_INCREASE', 25))
MAX_MARKET_DECREASE = int(os.environ.get('MAX_MARKET_DECREASE', 15))
AI_REVIEW_REQUIRED = os.environ.get('AI_REVIEW_REQUIRED', 'true').lower() == 'true'

MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
