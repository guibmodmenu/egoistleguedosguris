import os
import secrets
from flask import Flask, session, render_template, request
from sqlalchemy import text
from config import DATABASE_URI, SECRET_KEY, MAX_UPLOAD_SIZE, ALLOWED_EXTENSIONS
from models import db, Season, DEFAULT_INITIAL_MARKET_VALUE, LEGACY_INITIAL_MARKET_VALUE


def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = SECRET_KEY

    # Session security
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['PERMANENT_SESSION_LIFETIME'] = 86400

    db.init_app(app)

    # CSRF token
    @app.before_request
    def csrf_protect():
        if request.method == 'POST':
            token = session.get('csrf_token')
            form_token = request.form.get('csrf_token')
            if not token or not form_token or token != form_token:
                if request.endpoint not in ('auth.login', 'auth.register', 'admin.api_club_players'):
                    from flask import abort
                    abort(403)

    @app.before_request
    def generate_csrf():
        if 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_hex(32)

    @app.context_processor
    def inject_csrf():
        return dict(csrf_token=session.get('csrf_token', ''))

    # Security headers
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

    from routes.auth import auth_bp
    from routes.player import player_bp
    from routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(player_bp)
    app.register_blueprint(admin_bp)

    @app.context_processor
    def inject_user():
        from models import User, Player
        user = None
        player = None
        if 'user_id' in session:
            user = db.session.get(User, session['user_id'])
            if user and user.player:
                player = user.player
        return dict(current_user=user, current_player=player)

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template('errors/500.html'), 500

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/404.html'), 403

    with app.app_context():
        # Fail startup if the configured database cannot be reached; never fall back
        # to a local database in production. create_all adds missing tables only.
        with db.engine.connect() as connection:
            connection.execute(text('SELECT 1'))
        db.create_all()
        # Move the previous hard-coded default for new signups only. Existing
        # SeasonPlayer market values and their histories are intentionally kept.
        migrated_seasons = Season.query.filter_by(
            status='ACTIVE', initial_market_value=LEGACY_INITIAL_MARKET_VALUE
        ).update(
            {'initial_market_value': DEFAULT_INITIAL_MARKET_VALUE},
            synchronize_session=False,
        )
        if migrated_seasons:
            db.session.commit()

    return app


app = create_app()


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
