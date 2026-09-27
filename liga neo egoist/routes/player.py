from flask import Blueprint, render_template, redirect, url_for, session, flash, jsonify, request
from models import db, Player, Season, SeasonPlayer, Club, Match, MatchPlayer, PlayerValueHistory
from decorators import login_required

player_bp = Blueprint('player', __name__)


@player_bp.route('/')
def index():
    return redirect(url_for('auth.login'))


@player_bp.route('/choose-club', methods=['GET', 'POST'])
@login_required
def choose_club():
    from models import User
    user = db.session.get(User, session['user_id'])
    if not user or not user.player:
        flash('Configure seu perfil primeiro.', 'warning')
        return redirect(url_for('auth.login'))

    player = user.player
    active_season = Season.query.filter_by(status='ACTIVE').first()

    if not active_season:
        flash('Nenhuma temporada ativa.', 'error')
        return redirect(url_for('player.dashboard'))

    existing = SeasonPlayer.query.filter_by(
        season_id=active_season.id, player_id=player.id
    ).first()
    if existing:
        flash('Você já está em um clube nesta temporada.', 'info')
        return redirect(url_for('player.dashboard'))

    clubs = Club.query.filter_by(active=True).all()
    club_counts = {}
    for club in clubs:
        count = SeasonPlayer.query.filter_by(
            season_id=active_season.id, club_id=club.id
        ).count()
        club_counts[club.id] = count

    if request.method == 'POST':
        club_id = request.form.get('club_id', type=int)
        if not club_id:
            flash('Selecione um clube.', 'error')
            return render_template('choose_club.html', clubs=clubs, club_counts=club_counts, active_season=active_season)

        club = db.session.get(Club, club_id)
        if not club or not club.active:
            flash('Clube inválido.', 'error')
            return redirect(url_for('player.choose_club'))

        count = SeasonPlayer.query.filter_by(
            season_id=active_season.id, club_id=club_id
        ).count()
        if count >= club.max_players:
            flash(f'{club.name} está cheio ({club.max_players} jogadores).', 'error')
            return redirect(url_for('player.choose_club'))

        sp = SeasonPlayer(
            season_id=active_season.id,
            player_id=player.id,
            club_id=club_id,
            starting_market_value=active_season.initial_market_value,
            current_market_value=active_season.initial_market_value,
        )
        db.session.add(sp)
        db.session.commit()
        flash(f'Você entrou no {club.name}! Bem-vindo!', 'success')
        return redirect(url_for('player.dashboard'))

    return render_template('choose_club.html', clubs=clubs, club_counts=club_counts, active_season=active_season)


@player_bp.route('/dashboard')
@login_required
def dashboard():
    from models import User
    user = db.session.get(User, session['user_id'])
    if not user or not user.player:
        flash('Configure seu perfil primeiro.', 'warning')
        return redirect(url_for('auth.login'))

    player = user.player
    active_season = Season.query.filter_by(status='ACTIVE').first()
    season_player = None
    club = None
    recent_match = None
    recent_value_change = None

    if active_season:
        season_player = SeasonPlayer.query.filter_by(
            season_id=active_season.id, player_id=player.id
        ).first()
        if not season_player:
            return redirect(url_for('player.choose_club'))
        club = db.session.get(Club, season_player.club_id)
        last_mp = MatchPlayer.query.join(Match).filter(
            Match.season_id == active_season.id,
            MatchPlayer.season_player_id == season_player.id,
            Match.status == 'FINISHED'
        ).order_by(Match.scheduled_at.desc()).first()
        if last_mp:
            recent_match = {'match': db.session.get(Match, last_mp.match_id), 'stats': last_mp}
        recent_value_change = PlayerValueHistory.query.filter_by(
            season_player_id=season_player.id
        ).order_by(PlayerValueHistory.created_at.desc()).first()

    return render_template('dashboard.html', player=player, season_player=season_player,
                           club=club, active_season=active_season,
                           recent_match=recent_match, recent_value_change=recent_value_change)


@player_bp.route('/rank')
def rank():
    active_season = Season.query.filter_by(status='ACTIVE').first()
    sort_by = request.args.get('sort', 'value')
    players_data = []

    if active_season:
        season_players = SeasonPlayer.query.filter_by(season_id=active_season.id).all()
        for sp in season_players:
            player = db.session.get(Player, sp.player_id)
            club = db.session.get(Club, sp.club_id)
            if player and club:
                latest_value_change = PlayerValueHistory.query.filter_by(
                    season_player_id=sp.id
                ).order_by(PlayerValueHistory.id.desc()).first()
                players_data.append({
                    'player': player, 'season_player': sp, 'club': club,
                    'value_change': latest_value_change,
                })

        sort_keys = {'goals': 'goals', 'assists': 'assists', 'rating': 'rating_average'}
        key = sort_keys.get(sort_by, 'current_market_value')
        players_data.sort(key=lambda x: getattr(x['season_player'], key), reverse=True)

    return render_template('rank.html', players_data=players_data,
                           active_season=active_season, sort_by=sort_by)


@player_bp.route('/player/<int:player_id>')
def player_profile(player_id):
    player = db.session.get(Player, player_id)
    if not player:
        flash('Jogador não encontrado.', 'error')
        return redirect(url_for('player.rank'))

    active_season = Season.query.filter_by(status='ACTIVE').first()
    season_player = None
    club = None
    value_history = []
    match_history = []

    if active_season:
        season_player = SeasonPlayer.query.filter_by(
            season_id=active_season.id, player_id=player.id
        ).first()
        if season_player:
            club = db.session.get(Club, season_player.club_id)
            value_history = PlayerValueHistory.query.filter_by(
                season_player_id=season_player.id
            ).order_by(PlayerValueHistory.created_at.desc()).all()
            for mp in MatchPlayer.query.filter_by(season_player_id=season_player.id).all():
                match = db.session.get(Match, mp.match_id)
                if match:
                    match_history.append({'match': match, 'stats': mp})

    return render_template('player_profile.html', player=player, season_player=season_player,
                           club=club, active_season=active_season,
                           value_history=value_history, match_history=match_history)


@player_bp.route('/matches')
def matches():
    active_season = Season.query.filter_by(status='ACTIVE').first()
    matches_list = []
    if active_season:
        matches_list = Match.query.filter_by(season_id=active_season.id)\
            .order_by(Match.scheduled_at.desc()).all()
    return render_template('matches.html', matches_list=matches_list, active_season=active_season)


@player_bp.route('/matches/<int:match_id>')
def match_detail(match_id):
    match = db.session.get(Match, match_id)
    if not match:
        flash('Partida não encontrada.', 'error')
        return redirect(url_for('player.matches'))

    players_data = []
    for mp in match.players:
        sp = db.session.get(SeasonPlayer, mp.season_player_id)
        if sp:
            player = db.session.get(Player, sp.player_id)
            club = db.session.get(Club, sp.club_id)
            players_data.append({'match_player': mp, 'season_player': sp, 'player': player, 'club': club})

    return render_template('match_detail.html', match=match, players_data=players_data)


@player_bp.route('/market')
def market():
    active_season = Season.query.filter_by(status='ACTIVE').first()
    players_data = []
    if active_season:
        for sp in SeasonPlayer.query.filter_by(season_id=active_season.id).all():
            player = db.session.get(Player, sp.player_id)
            club = db.session.get(Club, sp.club_id)
            if player and club:
                players_data.append({'player': player, 'season_player': sp, 'club': club})
        players_data.sort(key=lambda x: x['season_player'].current_market_value, reverse=True)
    return render_template('market.html', players_data=players_data, active_season=active_season)


@player_bp.route('/profile')
@login_required
def profile():
    from models import User
    user = db.session.get(User, session['user_id'])
    if not user or not user.player:
        flash('Configure seu perfil primeiro.', 'warning')
        return redirect(url_for('auth.login'))
    player = user.player
    active_season = Season.query.filter_by(status='ACTIVE').first()
    season_player = None
    club = None
    if active_season:
        season_player = SeasonPlayer.query.filter_by(
            season_id=active_season.id, player_id=player.id
        ).first()
        if season_player:
            club = db.session.get(Club, season_player.club_id)
    return render_template('profile.html', player=player, season_player=season_player,
                           club=club, active_season=active_season)


@player_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def profile_edit():
    from models import User
    user = db.session.get(User, session['user_id'])
    if not user or not user.player:
        flash('Configure seu perfil primeiro.', 'warning')
        return redirect(url_for('auth.login'))
    player = user.player
    if request.method == 'POST':
        player.nickname = request.form.get('nickname', player.nickname).strip()
        player.display_name = request.form.get('display_name', player.display_name).strip()
        player.position = request.form.get('position', player.position)
        player.country_code = request.form.get('country_code', player.country_code)
        player.number = request.form.get('number', player.number, type=int)
        player.bio = request.form.get('bio', player.bio)
        player.icon_key = request.form.get('icon_key', player.icon_key)
        db.session.commit()
        flash('Perfil atualizado!', 'success')
        return redirect(url_for('player.profile'))
    return render_template('profile_edit.html', player=player)


@player_bp.route('/tasks')
@login_required
def tasks():
    return render_template('tasks.html')


@player_bp.route('/career')
@login_required
def career():
    from models import User
    user = db.session.get(User, session['user_id'])
    player = user.player if user else None
    active_season = Season.query.filter_by(status='ACTIVE').first()
    season_player = None
    club = None
    if active_season and player:
        season_player = SeasonPlayer.query.filter_by(
            season_id=active_season.id, player_id=player.id
        ).first()
        if season_player:
            club = db.session.get(Club, season_player.club_id)
    return render_template('career.html', player=player, season_player=season_player,
                           club=club, active_season=active_season)


@player_bp.route('/achievements')
@login_required
def achievements():
    return render_template('achievements.html')


@player_bp.route('/api/rank/<int:player_id>')
def api_player_detail(player_id):
    player = db.session.get(Player, player_id)
    if not player:
        return jsonify({'error': 'Jogador não encontrado'}), 404

    active_season = Season.query.filter_by(status='ACTIVE').first()
    season_player = None
    club = None

    if active_season:
        season_player = SeasonPlayer.query.filter_by(
            season_id=active_season.id, player_id=player.id
        ).first()
        if season_player:
            club = db.session.get(Club, season_player.club_id)

    if not season_player:
        return jsonify({'error': 'Jogador não participa da temporada ativa'}), 404

    value_history = PlayerValueHistory.query.filter_by(
        season_player_id=season_player.id
    ).order_by(PlayerValueHistory.created_at.desc()).limit(10).all()

    return jsonify({
        'player': {
            'id': player.id, 'nickname': player.nickname,
            'display_name': player.display_name, 'icon_key': player.icon_key,
            'position': player.position, 'country_code': player.country_code,
            'number': player.number,
        },
        'club': {
            'id': club.id, 'name': club.name, 'short_name': club.short_name,
            'primary_color': club.primary_color,
        } if club else None,
        'stats': {
            'current_market_value': season_player.current_market_value,
            'overall': season_player.overall, 'matches': season_player.matches,
            'goals': season_player.goals, 'assists': season_player.assists,
            'rating_average': season_player.rating_average,
            'mvp_count': season_player.mvp_count,
            'wins': season_player.wins, 'draws': season_player.draws,
            'losses': season_player.losses,
        },
        'value_history': [{
            'previous_value': vh.previous_value, 'change': vh.change,
            'change_percent': vh.change_percent, 'new_value': vh.new_value,
            'reason': vh.reason, 'source': vh.source,
            'created_at': vh.created_at.isoformat() if vh.created_at else None,
        } for vh in value_history],
    })
