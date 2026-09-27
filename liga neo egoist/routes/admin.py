import uuid
import os
from flask import Blueprint, render_template, redirect, url_for, session, flash, request, jsonify
from werkzeug.utils import secure_filename
from models import db, User, Player, Season, SeasonPlayer, SeasonPlayerAttributes, SeasonClub, Club, Match, MatchPlayer, Invite, PlayerValueHistory
from decorators import admin_required
from werkzeug.security import generate_password_hash
from datetime import datetime, timezone
from config import MAX_UPLOAD_SIZE, ALLOWED_EXTENSIONS, MAX_MARKET_INCREASE

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
                attribute_record = SeasonPlayerAttributes.query.filter_by(
                    season_player_id=sp.id
                ).first()
                default_attribute = max(0, min(100, int(round(sp.overall))))
                attribute_values = {
                    'defense': attribute_record.defense if attribute_record else default_attribute,
                    'passing': attribute_record.passing if attribute_record else default_attribute,
                    'physical': attribute_record.physical if attribute_record else default_attribute,
                    'speed': attribute_record.speed if attribute_record else default_attribute,
                    'attack': attribute_record.attack if attribute_record else default_attribute,
                }
                players_data.append({
                    'player': player, 'season_player': sp, 'club': club,
                    'attribute_values': attribute_values,
                })
        players_data.sort(key=lambda x: x['season_player'].current_market_value, reverse=True)
    return render_template('admin/players.html', players_data=players_data, active_season=active_season)


@admin_bp.route('/players/<int:season_player_id>/overall', methods=['POST'])
@admin_required
def player_update_overall(season_player_id):
    active_season = Season.query.filter_by(status='ACTIVE').first()
    if not active_season:
        flash('Não há uma temporada ativa para atualizar o overall.', 'error')
        return redirect(url_for('admin.players_list'))

    season_player = SeasonPlayer.query.filter_by(
        id=season_player_id, season_id=active_season.id
    ).first()
    if not season_player:
        flash('Jogador não encontrado na temporada ativa.', 'error')
        return redirect(url_for('admin.players_list'))

    stat_names = ('defense', 'passing', 'physical', 'speed', 'attack')
    attribute_values = {}
    for name in stat_names:
        value = request.form.get(name, type=int)
        if value is None or not 0 <= value <= 100:
            flash('Cada atributo deve estar entre 0 e 100.', 'error')
            return redirect(url_for('admin.players_list'))
        attribute_values[name] = value

    attribute_record = SeasonPlayerAttributes.query.filter_by(
        season_player_id=season_player.id
    ).first()
    if not attribute_record:
        attribute_record = SeasonPlayerAttributes(season_player_id=season_player.id)
        db.session.add(attribute_record)

    for name, value in attribute_values.items():
        setattr(attribute_record, name, value)

    season_player.overall = round(sum(attribute_values.values()) / len(stat_names))
    db.session.commit()

    player = db.session.get(Player, season_player.player_id)
    flash(f'Overall de {player.nickname if player else "jogador"} atualizado para {int(season_player.overall)}.', 'success')
    return redirect(url_for('admin.players_list'))


@admin_bp.route('/players/value', methods=['GET', 'POST'])
@admin_required
def player_value_change():
    active_season = Season.query.filter_by(status='ACTIVE').first()
    actions = {
        'goal': {
            'label': 'gol',
            'plural': 'gols',
            'stat': 'goals',
            'percent': (0.55 * 1.8 + 0.25 * 1.8) * 3,
        },
        'assist': {
            'label': 'assistência',
            'plural': 'assistências',
            'stat': 'assists',
            'percent': (0.55 * 1.2 + 0.25 * 1.2) * 3,
        },
        'tackle': {
            'label': 'desarme',
            'plural': 'desarmes',
            'stat': None,
            'percent': (0.55 * 0.15 + 0.15 * 0.18) * 3,
        },
        'save': {
            'label': 'defesa',
            'plural': 'defesas',
            'stat': None,
            'percent': (0.55 * 0.18 + 0.15 * 0.2) * 3,
        },
        'manual_loss': {
            'label': 'perda manual de valor',
            'plural': 'perda manual de valor',
            'stat': None,
            'mode': 'manual_loss',
        },
    }

    if request.method == 'POST':
        if not active_season:
            flash('Não há temporada ativa para alterar valores.', 'error')
            return redirect(url_for('admin.dashboard'))

        season_player_id = request.form.get('season_player_id', type=int)
        quantity = request.form.get('quantity', 1, type=int)
        action = actions.get(request.form.get('action', ''))
        season_player = SeasonPlayer.query.filter_by(
            id=season_player_id, season_id=active_season.id
        ).first()

        if not season_player or not action:
            flash('Selecione um jogador e uma ação válidos.', 'error')
            return redirect(url_for('admin.player_value_change'))

        player = db.session.get(Player, season_player.player_id)
        previous_value = int(season_player.current_market_value)

        if action.get('mode') == 'manual_loss':
            loss_amount = request.form.get('loss_amount', type=int)
            if not loss_amount or loss_amount <= 0 or previous_value <= 0:
                flash('Informe uma perda positiva; o valor atual do jogador precisa ser maior que zero.', 'error')
                return redirect(url_for('admin.player_value_change'))
            change_amount = -min(loss_amount, previous_value)
            new_value = previous_value + change_amount
            change_percent = round(change_amount * 100 / previous_value, 2)
            action_text = f"perda manual de ¥{abs(change_amount):,}"
            result_message = (
                f"Valor de {player.nickname if player else 'jogador'} reduzido em "
                f"¥{abs(change_amount):,} para ¥{new_value:,}."
            )
        else:
            if not quantity or not 1 <= quantity <= 100:
                flash('Informe uma quantidade de 1 a 100.', 'error')
                return redirect(url_for('admin.player_value_change'))
            change_percent = min(MAX_MARKET_INCREASE, round(action['percent'] * quantity, 2))
            change_amount = int(previous_value * change_percent / 100)
            new_value = max(0, previous_value + change_amount)
            action_text = action['label'] if quantity == 1 else action['plural']
            result_message = (
                f"Ação registrada: {quantity} {action_text} para "
                f"{player.nickname if player else 'Jogador'}. Novo valor ¥{new_value:,}."
            )

        if action['stat']:
            setattr(season_player, action['stat'], getattr(season_player, action['stat']) + quantity)

        season_player.current_market_value = new_value
        db.session.add(PlayerValueHistory(
            season_player_id=season_player.id,
            previous_value=previous_value,
            change=change_amount,
            change_percent=change_percent,
            new_value=new_value,
            reason=f"Ação manual: {quantity} {action_text}",
            source='ADMIN',
        ))
        db.session.commit()

        flash(result_message, 'success')
        return redirect(url_for('admin.player_value_change'))

    players_data = []
    if active_season:
        for sp in SeasonPlayer.query.filter_by(season_id=active_season.id).all():
            player = db.session.get(Player, sp.player_id)
            club = db.session.get(Club, sp.club_id)
            if player:
                players_data.append({'player': player, 'season_player': sp, 'club': club})
        players_data.sort(key=lambda item: item['player'].nickname.lower())

    return render_template('admin/player_value.html', players_data=players_data,
                           active_season=active_season)


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
