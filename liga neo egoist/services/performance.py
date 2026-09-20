def calculate_rating(match_player):
    minutes = match_player.minutes
    if minutes <= 0:
        return 0.0

    goals = match_player.goals
    assists = match_player.assists
    shots = match_player.shots
    shots_on_target = match_player.shots_on_target
    passes = match_player.passes
    accurate_passes = match_player.accurate_passes
    chances_created = match_player.chances_created
    tackles = match_player.tackles
    interceptions = match_player.interceptions
    clearances = match_player.clearances
    blocks = match_player.blocks
    saves = match_player.saves
    goals_conceded = match_player.goals_conceded
    yellow_cards = match_player.yellow_cards
    red_cards = match_player.red_cards
    clean_sheet = match_player.clean_sheet
    mvp = match_player.mvp

    base = 5.0
    minutes_factor = min(minutes / 90.0, 1.0) * 0.5

    attack = (goals * 1.8 + assists * 1.2 + shots_on_target * 0.15 + chances_created * 0.2)

    defense = (tackles * 0.15 + interceptions * 0.2 + clearances * 0.08 + blocks * 0.1 + saves * 0.18)

    pass_accuracy = (accurate_passes / passes * 0.3) if passes > 0 else 0

    discipline = yellow_cards * 0.2 + red_cards * 1.0
    goal_penalty = goals_conceded * 0.15 if not clean_sheet else 0
    clean_sheet_bonus = 0.5 if clean_sheet else 0
    mvp_bonus = 0.3 if mvp else 0

    raw = base + minutes_factor + attack + defense + pass_accuracy - discipline - goal_penalty + clean_sheet_bonus + mvp_bonus
    rating = max(0.0, min(10.0, round(raw, 1)))

    return rating
