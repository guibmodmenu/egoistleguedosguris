import os
import secrets

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Use PostgreSQL in production; SQLite is a local-development fallback only.
_environment_names = ('APP_ENV', 'ENVIRONMENT', 'FLASK_ENV', 'DEPLOYMENT_ENV')
IS_PRODUCTION = (
    any(os.environ.get(name, '').strip().lower() in {'production', 'prod'}
        for name in _environment_names)
    or os.environ.get('RENDER', '').strip().lower() in {'true', '1', 'yes'}
    or bool(os.environ.get('RENDER_SERVICE_ID', '').strip())
)

DATABASE_URI = os.environ.get('DATABASE_URL', '').strip()
if not DATABASE_URI:
    if IS_PRODUCTION:
        raise RuntimeError(
            'DATABASE_URL is required in production. Configure the Render PostgreSQL '
            'database connection; SQLite fallback is disabled.'
        )
    DATABASE_PATH = os.path.join(BASE_DIR, 'database', 'league.db')
    DATABASE_URI = f'sqlite:///{DATABASE_PATH}'

# Normalize PostgreSQL URL schemes used by hosting providers.
if DATABASE_URI.startswith('postgres://'):
    DATABASE_URI = DATABASE_URI.replace('postgres://', 'postgresql://', 1)
elif DATABASE_URI.startswith('postgresql+psycopg://'):
    DATABASE_URI = DATABASE_URI.replace('postgresql+psycopg://', 'postgresql+psycopg2://', 1)

if IS_PRODUCTION and not DATABASE_URI.startswith(('postgresql://', 'postgresql+psycopg2://')):
    raise RuntimeError(
        'Production must use PostgreSQL through DATABASE_URL; a SQLite database URL is not allowed.'
    )

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
