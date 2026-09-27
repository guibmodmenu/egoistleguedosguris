from config import MAX_MARKET_INCREASE, MAX_MARKET_DECREASE


def apply_market_change(season_player, match_player, match):
    goals = match_player.goals
    assists = match_player.assists
    tackles = match_player.tackles
    interceptions = match_player.interceptions
    clearances = match_player.clearances
    saves = match_player.saves
    yellow_cards = match_player.yellow_cards
    red_cards = match_player.red_cards
    minutes = match_player.minutes
    rating = match_player.rating
    clean_sheet = match_player.clean_sheet
    mvp = match_player.mvp

    home_won = (match.home_club_id == season_player.club_id and match.home_score > match.away_score)
    away_won = (match.away_club_id == season_player.club_id and match.away_score > match.home_score)
    team_won = home_won or away_won
    team_draw = match.home_score == match.away_score

    attacking = goals * 1.8 + assists * 1.2 + match_player.shots_on_target * 0.25
    defending = tackles * 0.18 + interceptions * 0.22 + clearances * 0.1 + blocks * 0.12 + saves * 0.2
    discipline = yellow_cards * 0.3 + red_cards * 1.5
    team_factor = 0.5 if team_won else (0.1 if team_draw else -0.35)

    score = max(0, min(10, rating * 0.55 + attacking * 0.25 + defending * 0.15 + team_factor - discipline * 0.1))
    pct = max(-MAX_MARKET_DECREASE, min(MAX_MARKET_INCREASE, round((score - 6) * 3, 2)))

    if minutes <= 0:
        pct = min(pct, -5)

    if mvp:
        pct += 2

    if clean_sheet:
        pct += 1

    return max(-MAX_MARKET_DECREASE, min(MAX_MARKET_INCREASE, round(pct, 2)))
