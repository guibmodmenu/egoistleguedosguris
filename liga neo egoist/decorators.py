from functools import wraps
from flask import session, redirect, url_for, flash


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Você precisa estar logado.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Você precisa estar logado.', 'warning')
            return redirect(url_for('auth.login'))
        if session.get('role') not in ('ADMIN', 'SUPER_ADMIN'):
            flash('Acesso negado. Somente administradores.', 'error')
            return redirect(url_for('player.dashboard'))
        return f(*args, **kwargs)
    return decorated_function
