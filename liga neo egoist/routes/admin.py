import uuid
import os
from flask import Blueprint, render_template, redirect, url_for, session, flash, request, jsonify
from werkzeug.utils import secure_filename
from models import db, User, Player, Season, SeasonPlayer, SeasonClub, Club, Match, MatchPlayer, Invite
from decorators import admin_required
from werkzeug.security import generate_password_hash
from datetime import datetime, timezone
from config import MAX_UPLOAD_SIZE, ALLOWED_EXTENSIONS

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'static', 'uploads')

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def validate_upload(file):
    if not file or not file.filename:
        return False, 'Nenhum arquivo selecionado.'
    if not allowed_file(file.filename):
        return False, 'Formato nao suportado. Use PNG, JPG, GIF ou WebP.'
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > MAX_UPLOAD_SIZE:
        max_mb = MAX_UPLOAD_SIZE // (1024 * 1024)
        return False, f'Arquivo muito grande. Maximo: {max_mb}MB.'
    return True, None


@admin_bp.route('/')
@admin_required
def dashboard():
    active_season = Season.query.filter_by(status='ACTIVE').first()
    stats = {'players': 0, 'matches': 0, 'pending': 0, 'finished': 0}
    recent_matches = []

    if active_season:
        stats['players'] = SeasonPlayer.query.filter_by(season_id=active_season.id).count()
        all_matches = Match.query.filter_by(season_id=active_season.id)\
            .order_by(Match.scheduled_at.desc()).all()
        stats['matches'] = len(all_matches)
        stats['pending'] = sum(1 for m in all_matches if m.status == 'SCHEDULED')
        stats['finished'] = sum(1 for m in all_matches if m.status == 'FINISHED')
        recent_matches = all_matches[:5]

    return render_template('admin/dashboard.html', stats=stats,
                           recent_matches=recent_matches, active_season=active_season)


@admin_bp.route('/matches/new', methods=['GET', 'POST'])
@admin_required
def match_new():
    active_season = Season.query.filter_by(status='ACTIVE').first()
    clubs = Club.query.filter_by(active=True).all()

    if request.method == 'POST':
        home_club_id = request.form.get('home_club_id', type=int)
        away_club_id = request.form.get('away_club_id', type=int)
        home_score = request.form.get('home_score', 0, type=int)
        away_score = request.form.get('away_score', 0, type=int)
        scheduled_at = request.form.get('scheduled_at', '')
        notes = request.form.get('notes', '')

        if home_club_id == away_club_id:
            flash('Os clubes devem ser diferentes.', 'error')
            return render_template('admin/match_form.html', clubs=clubs, active_season=active_season)

        match = Match(
            season_id=active_season.id,
            home_club_id=home_club_id,
            away_club_id=away_club_id,
            home_score=home_score,
            away_score=away_score,
            status='FINISHED',
            scheduled_at=datetime.fromisoformat(scheduled_at) if scheduled_at else datetime.now(timezone.utc),
            notes=notes,
        )
        db.session.add(match)
        db.session.flush()

        player_ids = request.form.getlist('player_ids')
        for pid in player_ids:
            sp = SeasonPlayer.query.filter_by(season_id=active_season.id, player_id=int(pid)).first()
            if not sp:
                continue

            mp = MatchPlayer(
                match_id=match.id,
                season_player_id=sp.id,
                minutes=request.form.get(f'minutes_{pid}', 0, type=int),
                goals=request.form.get(f'goals_{pid}', 0, type=int),
                assists=request.form.get(f'assists_{pid}', 0, type=int),
                shots=request.form.get(f'shots_{pid}', 0, type=int),
                shots_on_target=request.form.get(f'shots_on_target_{pid}', 0, type=int),
                passes=request.form.get(f'passes_{pid}', 0, type=int),
                accurate_passes=request.form.get(f'accurate_passes_{pid}', 0, type=int),
                chances_created=request.form.get(f'chances_created_{pid}', 0, type=int),
                tackles=request.form.get(f'tackles_{pid}', 0, type=int),
                interceptions=request.form.get(f'interceptions_{pid}', 0, type=int),
                clearances=request.form.get(f'clearances_{pid}', 0, type=int),
                blocks=request.form.get(f'blocks_{pid}', 0, type=int),
                saves=request.form.get(f'saves_{pid}', 0, type=int),
                goals_conceded=request.form.get(f'goals_conceded_{pid}', 0, type=int),
                yellow_cards=request.form.get(f'yellow_cards_{pid}', 0, type=int),
                red_cards=request.form.get(f'red_cards_{pid}', 0, type=int),
                clean_sheet=request.form.get(f'clean_sheet_{pid}') == 'on',
                rating=request.form.get(f'rating_{pid}', 0.0, type=float),
                mvp=request.form.get(f'mvp_{pid}') == 'on',
            )
            db.session.add(mp)

        db.session.commit()
        flash('Partida registrada com sucesso!', 'success')
        return redirect(url_for('admin.match_process', match_id=match.id))

    return render_template('admin/match_form.html', clubs=clubs, active_season=active_season)


@admin_bp.route('/matches/<int:match_id>')
@admin_required
def match_detail(match_id):
    match = db.session.get(Match, match_id)
    if not match:
        flash('Partida não encontrada.', 'error')
        return redirect(url_for('admin.dashboard'))

    players_data = []
    for mp in match.players:
        sp = db.session.get(SeasonPlayer, mp.season_player_id)
        if sp:
            player = db.session.get(Player, sp.player_id)
            players_data.append({'match_player': mp, 'season_player': sp, 'player': player})

    return render_template('admin/match_detail.html', match=match, players_data=players_data)


@admin_bp.route('/matches/<int:match_id>/process')
@admin_required
def match_process(match_id):
    from services.performance import calculate_rating
    from services.market import apply_market_change

    match = db.session.get(Match, match_id)
    if not match:
        flash('Partida não encontrada.', 'error')
        return redirect(url_for('admin.dashboard'))

    if match.processedAt:
        flash('Esta partida já foi processada.', 'info')
        return redirect(url_for('admin.match_detail', match_id=match.id))

    for mp in match.players:
        rating = calculate_rating(mp)
        mp.rating = rating

        sp = db.session.get(SeasonPlayer, mp.season_player_id)
        if sp:
            sp.matches += 1
            sp.goals += mp.goals
            sp.assists += mp.assists
            if mp.mvp:
                sp.mvp_count += 1

            total_rating = sp.rating_average * (sp.matches - 1) + rating
            sp.rating_average = round(total_rating / sp.matches, 2) if sp.matches > 0 else 0

            home_club_id = match.home_club_id
            player_club_id = sp.club_id
            if match.home_score > match.away_score:
                sp.wins += 1 if player_club_id == home_club_id else 0
                sp.losses += 1 if player_club_id != home_club_id else 0
            elif match.home_score < match.away_score:
                sp.wins += 1 if player_club_id != home_club_id else 0
                sp.losses += 1 if player_club_id == home_club_id else 0
            else:
                sp.draws += 1

            change_pct = apply_market_change(sp, mp, match)
            change_amount = int(sp.current_market_value * change_pct / 100)
            new_value = max(0, int(sp.current_market_value) + change_amount)
            from models import PlayerValueHistory
            history = PlayerValueHistory(
                season_player_id=sp.id,
                match_id=match.id,
                previous_value=sp.current_market_value,
                change=change_amount,
                change_percent=round(change_pct, 2),
                new_value=new_value,
                reason=f"Partida processada - Rating {rating:.1f}",
                source='SYSTEM',
            )
            sp.current_market_value = new_value
            sp.overall = round(sp.overall * 0.9 + rating * 10 * 0.1, 1)
            db.session.add(history)

    home_sc = SeasonClub.query.filter_by(season_id=match.season_id, club_id=match.home_club_id).first()
    away_sc = SeasonClub.query.filter_by(season_id=match.season_id, club_id=match.away_club_id).first()

    if home_sc and away_sc:
        home_sc.goals_for += match.home_score
        home_sc.goals_against += match.away_score
        away_sc.goals_for += match.away_score
        away_sc.goals_against += match.home_score
        if match.home_score > match.away_score:
            home_sc.wins += 1; home_sc.points += 3
            away_sc.losses += 1
        elif match.home_score < match.away_score:
            away_sc.wins += 1; away_sc.points += 3
            home_sc.losses += 1
        else:
            home_sc.draws += 1; home_sc.points += 1
            away_sc.draws += 1; away_sc.points += 1

    match.processedAt = datetime.now(timezone.utc)
    db.session.commit()
    flash('Partida processada com sucesso!', 'success')
    return redirect(url_for('admin.match_detail', match_id=match.id))


@admin_bp.route('/players')
@admin_required
def players_list():
    active_season = Season.query.filter_by(status='ACTIVE').first()
    players_data = []
    if active_season:
        for sp in SeasonPlayer.query.filter_by(season_id=active_season.id).all():
            player = db.session.get(Player, sp.player_id)
            club = db.session.get(Club, sp.club_id)
            if player:
                players_data.append({'player': player, 'season_player': sp, 'club': club})
        players_data.sort(key=lambda x: x['season_player'].current_market_value, reverse=True)
    return render_template('admin/players.html', players_data=players_data, active_season=active_season)


@admin_bp.route('/players/<int:player_id>/icon', methods=['POST'])
@admin_required
def player_update_icon(player_id):
    player = db.session.get(Player, player_id)
    if not player:
        flash('Jogador não encontrado.', 'error')
        return redirect(url_for('admin.players_list'))

    icon_key = request.form.get('icon_key', 'zap')
    valid_icons = ['zap','flame','crosshair','shield','star','skull','orbit','ghost','sparkles','target','hexagon']
    if icon_key not in valid_icons:
        flash('Ícone inválido.', 'error')
        return redirect(url_for('admin.players_list'))

    player.icon_key = icon_key
    db.session.commit()
    flash(f'Ícone de {player.nickname} atualizado!', 'success')
    return redirect(url_for('admin.players_list'))


@admin_bp.route('/players/<int:player_id>/photo', methods=['POST'])
@admin_required
def player_update_photo(player_id):
    player = db.session.get(Player, player_id)
    if not player:
        flash('Jogador não encontrado.', 'error')
        return redirect(url_for('admin.players_list'))

    if 'photo' in request.files:
        file = request.files['photo']
        valid, err = validate_upload(file)
        if not valid:
            flash(err, 'error')
            return redirect(url_for('admin.players_list'))
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"player_{player.id}_{uuid.uuid4().hex[:8]}.{ext}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        player.avatar_url = f"/static/uploads/{filename}"
        db.session.commit()
        flash(f'Foto de {player.nickname} atualizada!', 'success')
        return redirect(url_for('admin.players_list'))
    elif 'photo_url' in request.form:
        url = request.form.get('photo_url', '').strip()
        if url:
            player.avatar_url = url
            db.session.commit()
            flash(f'Foto de {player.nickname} atualizada!', 'success')
            return redirect(url_for('admin.players_list'))
        else:
            flash('URL da foto não pode ser vazia.', 'error')

    return redirect(url_for('admin.players_list'))


@admin_bp.route('/invites')
@admin_required
def invites_list():
    invites = Invite.query.order_by(Invite.created_at.desc()).all()
    return render_template('admin/invites.html', invites=invites)


@admin_bp.route('/invites/new', methods=['POST'])
@admin_required
def invite_new():
    code = str(uuid.uuid4())[:8].upper()
    max_uses = request.form.get('max_uses', 1, type=int)
    invite = Invite(code=code, max_uses=max_uses, created_by=session['user_id'])
    db.session.add(invite)
    db.session.commit()
    flash(f'Convite criado: {code}', 'success')
    return redirect(url_for('admin.invites_list'))


@admin_bp.route('/api/players/<int:club_id>')
@admin_required
def api_club_players(club_id):
    from flask import jsonify
    active_season = Season.query.filter_by(status='ACTIVE').first()
    if not active_season:
        return jsonify([])

    season_players = SeasonPlayer.query.filter_by(
        season_id=active_season.id, club_id=club_id
    ).all()

    result = []
    for sp in season_players:
        player = db.session.get(Player, sp.player_id)
        club = db.session.get(Club, sp.club_id)
        if player:
            result.append({
                'id': player.id,
                'nickname': player.nickname,
                'display_name': player.display_name,
                'icon_key': player.icon_key,
                'position': player.position,
                'club': club.name if club else '',
                'season_player_id': sp.id,
            })

    return jsonify(result)


@admin_bp.route('/invites/<int:invite_id>/disable', methods=['POST'])
@admin_required
def invite_disable(invite_id):
    invite = db.session.get(Invite, invite_id)
    if invite:
        invite.status = 'DISABLED'
        db.session.commit()
        flash('Convite desativado.', 'info')
    return redirect(url_for('admin.invites_list'))


@admin_bp.route('/clubs')
@admin_required
def clubs_list():
    all_clubs = Club.query.order_by(Club.name).all()
    active_season = Season.query.filter_by(status='ACTIVE').first()
    club_data = []
    for club in all_clubs:
        player_count = 0
        if active_season:
            player_count = SeasonPlayer.query.filter_by(
                season_id=active_season.id, club_id=club.id
            ).count()
        club_data.append({'club': club, 'player_count': player_count})
    return render_template('admin/clubs.html', club_data=club_data, active_season=active_season)


@admin_bp.route('/clubs/<int:club_id>/toggle', methods=['POST'])
@admin_required
def club_toggle(club_id):
    club = db.session.get(Club, club_id)
    if not club:
        flash('Clube nao encontrado.', 'error')
        return redirect(url_for('admin.clubs_list'))

    active_season = Season.query.filter_by(status='ACTIVE').first()
    if active_season:
        player_count = SeasonPlayer.query.filter_by(
            season_id=active_season.id, club_id=club.id
        ).count()
        if player_count > 0 and club.active:
            flash(f'Nao e possivel desativar {club.name} — tem {player_count} jogador(es) neste clube.', 'error')
            return redirect(url_for('admin.clubs_list'))

    club.active = not club.active
    status = 'ativado' if club.active else 'desativado'
    db.session.commit()
    flash(f'{club.name} foi {status}!', 'success')
    return redirect(url_for('admin.clubs_list'))


@admin_bp.route('/clubs/<int:club_id>/logo', methods=['POST'])
@admin_required
def club_update_logo(club_id):
    club = db.session.get(Club, club_id)
    if not club:
        flash('Clube não encontrado.', 'error')
        return redirect(url_for('admin.clubs_list'))

    if 'logo' in request.files:
        file = request.files['logo']
        valid, err = validate_upload(file)
        if not valid:
            flash(err, 'error')
            return redirect(url_for('admin.clubs_list'))
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"club_{club.id}_{uuid.uuid4().hex[:8]}.{ext}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        club.logo_url = f"/static/uploads/{filename}"
        db.session.commit()
        flash(f'Escudo de {club.name} atualizado!', 'success')
    elif 'logo_url' in request.form:
        url = request.form.get('logo_url', '').strip()
        club.logo_url = url if url else None
        db.session.commit()
        flash(f'Escudo de {club.name} atualizado!', 'success')

    return redirect(url_for('admin.clubs_list'))
