import uuid
import time
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Player, Invite

auth_bp = Blueprint('auth', __name__)

# Rate limiting: {ip: [timestamps]}
_login_attempts = {}
_MAX_ATTEMPTS = 5
_LOCKOUT_SECONDS = 300  # 5 minutes


def _is_rate_limited(ip):
    now = time.time()
    if ip in _login_attempts:
        _login_attempts[ip] = [t for t in _login_attempts[ip] if now - t < _LOCKOUT_SECONDS]
        if len(_login_attempts[ip]) >= _MAX_ATTEMPTS:
            return True
    return False


def _record_attempt(ip):
    _login_attempts.setdefault(ip, []).append(time.time())


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    ip = request.remote_addr

    if request.method == 'POST':
        if _is_rate_limited(ip):
            flash('Muitas tentativas. Aguarde 5 minutos.', 'error')
            return render_template('login.html')

        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(username=username).first()

        if not user or not check_password_hash(user.password_hash, password):
            _record_attempt(ip)
            flash('Usuario ou senha invalidos.', 'error')
            return render_template('login.html')

        session['user_id'] = user.id
        session['role'] = user.role
        session.permanent = True
        _login_attempts.pop(ip, None)
        flash(f'Bem-vindo, {user.player.nickname if user.player else user.username}!', 'success')
        return redirect(url_for('player.dashboard'))

    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    invite_code = request.args.get('code', '') or request.form.get('invite_code', '')

    if request.method == 'POST':
        invite_code = request.form.get('invite_code', '').strip()
        nickname = request.form.get('nickname', '').strip()
        password = request.form.get('password', '')

        if len(password) < 6:
            flash('A senha deve ter no minimo 6 caracteres.', 'error')
            return render_template('register.html', invite_code=invite_code)

        if len(nickname) < 2:
            flash('O nickname deve ter no minimo 2 caracteres.', 'error')
            return render_template('register.html', invite_code=invite_code)

        invite = Invite.query.filter_by(code=invite_code, status='ACTIVE').first()

        if not invite:
            flash('Código de convite inválido ou expirado.', 'error')
            return render_template('register.html', invite_code=invite_code)

        if invite.uses >= invite.max_uses:
            flash('Este convite já atingiu o número máximo de uso.', 'error')
            return render_template('register.html', invite_code=invite_code)

        existing_user = User.query.filter_by(username=nickname).first()
        if existing_user:
            flash('Este nickname já está em uso.', 'error')
            return render_template('register.html', invite_code=invite_code)

        user = User(
            username=nickname,
            password_hash=generate_password_hash(password),
            role='USER',
            status='ACTIVE'
        )
        db.session.add(user)
        db.session.flush()

        player = Player(
            user_id=user.id,
            nickname=nickname,
            display_name=nickname,
            icon_key='zap',
            position='MIDFIELDER'
        )
        db.session.add(player)
        db.session.flush()

        invite.uses += 1
        db.session.commit()

        session['user_id'] = user.id
        session['role'] = user.role
        flash('Conta criada com sucesso! Configure seu perfil.', 'success')
        return redirect(url_for('player.dashboard'))

    return render_template('register.html', invite_code=invite_code)


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Você saiu da conta.', 'info')
    return redirect(url_for('auth.login'))
