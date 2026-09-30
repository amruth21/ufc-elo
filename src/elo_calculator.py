"""
MMA ELO Rating Calculator

Implements the ELO formula with MMA-specific multipliers:
- Finish bonus (KO/TKO/Submission)
- Title fight multiplier
- Opponent strength multiplier
- Win streak multiplier
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


# ============================================================
# CONSTANTS - Adjust these to tune the ELO system
# ============================================================

STARTING_ELO = 1500.0
K_BASE = 32.0

# Finish bonus multiplier
M_FINISH_KO_SUB = 1.3  # For KO/TKO/Submission
M_FINISH_DECISION = 1.0  # For Decision

# Title fight multiplier
M_TITLE_FIGHT = 1.5
M_REGULAR_FIGHT = 1.0

# Opponent strength tiers
OPPONENT_TIERS = [
    (1400, 0.8),   # < 1400: weak opponent
    (1600, 1.0),   # 1400-1599: average
    (1800, 1.2),   # 1600-1799: strong
    (float('inf'), 1.4),  # >= 1800: elite
]

# Win streak multiplier (for winner's own streak)
STREAK_COEFFICIENT = 0.03
STREAK_MAX_MULTIPLIER = 1.3

# Opponent streak multipliers (streak breaker bonus / cold opponent penalty)
OPP_WIN_STREAK_COEFFICIENT = 0.02   # Bonus per opponent win streak
OPP_WIN_STREAK_MAX = 1.2            # Max 20% bonus for breaking big streaks
OPP_LOSE_STREAK_COEFFICIENT = 0.02  # Penalty per opponent lose streak  
OPP_LOSE_STREAK_MIN = 0.85          # Min 15% penalty for beating cold opponents

# Title defense streak multiplier (bonus for defending champions on title run)
# 
# IMPORTANT: Set ENABLE_TITLE_DEFENSE_STREAK_BONUS = False to disable this feature.
# When disabled, only regular win streaks are counted, not consecutive title defenses.
#
# This bonus only applies when:
# - Current fight is a title fight
# - Fighter is defending (previous fight was also a title win)
# - Fighter has title_defense_streak > 0
#
# Does NOT apply to fighters winning the title for the first time on a regular win streak.
ENABLE_TITLE_DEFENSE_STREAK_BONUS = True
TITLE_DEFENSE_STREAK_COEFFICIENT = 0.02  # Bonus per title defense in streak (+2% per defense)
TITLE_DEFENSE_STREAK_MAX = 1.15           # Max 15% bonus for long title runs (7+ defenses)


@dataclass
class FighterElo:
    """Track a fighter's ELO and stats."""
    id: str
    name: str
    elo: float = STARTING_ELO
    wins: int = 0
    losses: int = 0
    draws: int = 0
    win_streak: int = 0
    lose_streak: int = 0
    title_defense_streak: int = 0  # Consecutive title fight wins (defending champion)
    previous_fight_was_title_win: bool = False  # Track if previous fight was a title win
    peak_elo: float = STARTING_ELO
    fights: int = 0


def calculate_expected_probability(fighter_elo: float, opponent_elo: float) -> float:
    """
    Calculate expected win probability using ELO formula.
    
    E = 1 / (1 + 10^((Elo_opponent - Elo_fighter) / 400))
    """
    exponent = (opponent_elo - fighter_elo) / 400.0
    return 1.0 / (1.0 + math.pow(10, exponent))


def get_finish_multiplier(method: str, is_finish: bool) -> float:
    """Get multiplier based on fight result method."""
    if is_finish:
        return M_FINISH_KO_SUB
    return M_FINISH_DECISION


def get_title_multiplier(is_title_fight: bool) -> float:
    """Get multiplier for title fights."""
    return M_TITLE_FIGHT if is_title_fight else M_REGULAR_FIGHT


def get_opponent_multiplier(opponent_elo: float) -> float:
    """
    Get multiplier based on opponent's ELO.
    
    Uses tiered approach:
    - < 1400: 0.8 (weak)
    - 1400-1599: 1.0 (average)
    - 1600-1799: 1.2 (strong)
    - >= 1800: 1.4 (elite)
    """
    for threshold, multiplier in OPPONENT_TIERS:
        if opponent_elo < threshold:
            return multiplier
    return 1.4  # Default to elite


def get_opponent_multiplier_continuous(opponent_elo: float) -> float:
    """
    Alternative continuous formula for opponent strength.
    
    M_opponent = 0.8 + (opponent_elo - 1400) / 1000
    Clamped between 0.6 and 1.5
    """
    m = 0.8 + (opponent_elo - 1400) / 1000
    return max(0.6, min(1.5, m))


def get_streak_multiplier(win_streak: int) -> float:
    """
    Get win streak multiplier.
    
    M_streak = 1.0 + (win_streak × 0.03)
    Capped at 1.3 (30% bonus max)
    """
    m = 1.0 + (win_streak * STREAK_COEFFICIENT)
    return min(STREAK_MAX_MULTIPLIER, m)


def get_opponent_streak_multiplier(opp_win_streak: int, opp_lose_streak: int) -> float:
    """
    Get multiplier based on opponent's streak.
    
    - Beating opponent on WIN streak: BONUS (they're hot, harder to beat)
      M = 1.0 + (opp_win_streak × 0.02), max 1.2 (20% bonus)
    
    - Beating opponent on LOSE streak: PENALTY (they're cold, easier to beat)
      M = 1.0 - (opp_lose_streak × 0.02), min 0.85 (15% penalty)
    
    If opponent has neither streak, multiplier is 1.0.
    """
    if opp_win_streak > 0:
        # Opponent on win streak - bonus for breaking it
        m = 1.0 + (opp_win_streak * OPP_WIN_STREAK_COEFFICIENT)
        return min(OPP_WIN_STREAK_MAX, m)
    elif opp_lose_streak > 0:
        # Opponent on lose streak - penalty for beating cold fighter
        m = 1.0 - (opp_lose_streak * OPP_LOSE_STREAK_COEFFICIENT)
        return max(OPP_LOSE_STREAK_MIN, m)
    else:
        return 1.0


def get_title_defense_streak_multiplier(
    is_title_fight: bool,
    title_defense_streak: int,
    previous_fight_was_title_win: bool,
) -> float:
    """
    Get multiplier for title defense streak bonus.
    
    Only applies when:
    - Current fight is a title fight
    - Fighter is defending (previous fight was a title win)
    - Fighter has title defense streak > 0
    
    M_title_defense = 1.0 + (title_defense_streak × 0.02)
    Capped at 1.15 (15% bonus max)
    
    Set ENABLE_TITLE_DEFENSE_STREAK_BONUS = False to disable this feature.
    """
    if not ENABLE_TITLE_DEFENSE_STREAK_BONUS:
        return 1.0
    
    # Only apply if this is a title fight and fighter is defending
    if not is_title_fight:
        return 1.0
    
    # Fighter must be defending (previous fight was title win)
    if not previous_fight_was_title_win or title_defense_streak == 0:
        return 1.0
    
    # Calculate bonus: +2% per title defense in streak
    m = 1.0 + (title_defense_streak * TITLE_DEFENSE_STREAK_COEFFICIENT)
    return min(TITLE_DEFENSE_STREAK_MAX, m)


def calculate_k_factor(
    is_finish: bool,
    is_title_fight: bool,
    opponent_elo: float,
    win_streak: int,
    apply_streak: bool = True,
    opp_win_streak: int = 0,
    opp_lose_streak: int = 0,
    apply_opp_streak: bool = False,
    title_defense_streak: int = 0,
    previous_fight_was_title_win: bool = False,
) -> float:
    """
    Calculate the K-factor for ELO change.
    
    K = K_base × M_finish × M_title × M_opponent × M_streak × M_title_defense × M_opp_streak
    
    Args:
        is_finish: Whether fight ended by KO/TKO/Submission
        is_title_fight: Whether this is a title fight
        opponent_elo: Opponent's ELO before fight
        win_streak: Fighter's own win streak (for winner only)
        apply_streak: Whether to apply fighter's own streak bonus
        opp_win_streak: Opponent's win streak (bonus for breaking)
        opp_lose_streak: Opponent's lose streak (penalty for beating cold fighter)
        apply_opp_streak: Whether to apply opponent streak modifier
        title_defense_streak: Fighter's title defense streak (consecutive title wins)
        previous_fight_was_title_win: Whether fighter's previous fight was a title win
    """
    k = K_BASE
    k *= get_finish_multiplier("", is_finish)
    k *= get_title_multiplier(is_title_fight)
    k *= get_opponent_multiplier(opponent_elo)
    if apply_streak:
        k *= get_streak_multiplier(win_streak)
    # Title defense streak bonus (only for defending champions)
    k *= get_title_defense_streak_multiplier(
        is_title_fight, title_defense_streak, previous_fight_was_title_win
    )
    if apply_opp_streak:
        k *= get_opponent_streak_multiplier(opp_win_streak, opp_lose_streak)
    return k


def process_fight(
    fighter1: FighterElo,
    fighter2: FighterElo,
    winner_id: str,
    is_draw: bool,
    is_finish: bool,
    is_title_fight: bool,
) -> Tuple[float, float, float, float]:
    """
    Process a single fight and calculate ELO changes.
    
    Returns: (f1_elo_change, f2_elo_change, f1_new_elo, f2_new_elo)
    """
    # Calculate expected probabilities
    e1 = calculate_expected_probability(fighter1.elo, fighter2.elo)
    e2 = 1.0 - e1  # E2 = calculate_expected_probability(fighter2.elo, fighter1.elo)
    
    if is_draw:
        # Draw: both get partial ELO change (0.5 result), no streak bonuses
        k1 = calculate_k_factor(
            is_finish, is_title_fight, fighter2.elo, 0, apply_streak=False,
            title_defense_streak=0, previous_fight_was_title_win=False,
        )
        k2 = calculate_k_factor(
            is_finish, is_title_fight, fighter1.elo, 0, apply_streak=False,
            title_defense_streak=0, previous_fight_was_title_win=False,
        )
        
        delta1 = k1 * (0.5 - e1)
        delta2 = k2 * (0.5 - e2)
    elif winner_id == fighter1.id:
        # Fighter 1 wins
        # Winner gets: own streak bonus + opponent streak modifier + title defense streak
        k_winner = calculate_k_factor(
            is_finish, is_title_fight, fighter2.elo, 
            fighter1.win_streak, apply_streak=True,
            opp_win_streak=fighter2.win_streak,
            opp_lose_streak=fighter2.lose_streak,
            apply_opp_streak=True,
            title_defense_streak=fighter1.title_defense_streak,
            previous_fight_was_title_win=fighter1.previous_fight_was_title_win,
        )
        # Loser doesn't get streak bonuses
        k_loser = calculate_k_factor(
            is_finish, is_title_fight, fighter1.elo,
            0, apply_streak=False,
            title_defense_streak=0, previous_fight_was_title_win=False,
        )
        
        delta1 = k_winner * (1.0 - e1)
        delta2 = -k_loser * e2
    elif winner_id == fighter2.id:
        # Fighter 2 wins
        # Winner gets: own streak bonus + opponent streak modifier + title defense streak
        k_winner = calculate_k_factor(
            is_finish, is_title_fight, fighter1.elo,
            fighter2.win_streak, apply_streak=True,
            opp_win_streak=fighter1.win_streak,
            opp_lose_streak=fighter1.lose_streak,
            apply_opp_streak=True,
            title_defense_streak=fighter2.title_defense_streak,
            previous_fight_was_title_win=fighter2.previous_fight_was_title_win,
        )
        k_loser = calculate_k_factor(
            is_finish, is_title_fight, fighter2.elo,
            0, apply_streak=False,
            title_defense_streak=0, previous_fight_was_title_win=False,
        )
        
        delta1 = -k_loser * e1
        delta2 = k_winner * (1.0 - e2)
    else:
        # No winner recorded - treat as draw
        delta1 = 0.0
        delta2 = 0.0
    
    new_elo1 = round(fighter1.elo + delta1, 1)
    new_elo2 = round(fighter2.elo + delta2, 1)
    
    return (round(delta1, 1), round(delta2, 1), new_elo1, new_elo2)


def update_fighter_after_fight(
    fighter: FighterElo,
    won: bool,
    drew: bool,
    new_elo: float,
    is_title_fight: bool = False,
) -> None:
    """
    Update fighter stats after a fight.
    
    Args:
        fighter: Fighter to update
        won: Whether fighter won
        drew: Whether fight was a draw
        new_elo: Fighter's new ELO rating
        is_title_fight: Whether this was a title fight
    """
    fighter.elo = new_elo
    fighter.fights += 1
    
    if fighter.elo > fighter.peak_elo:
        fighter.peak_elo = fighter.elo
    
    if drew:
        fighter.draws += 1
        fighter.win_streak = 0
        fighter.lose_streak = 0
        fighter.title_defense_streak = 0
        fighter.previous_fight_was_title_win = False
    elif won:
        fighter.wins += 1
        fighter.win_streak += 1
        fighter.lose_streak = 0
        
        # Update title defense streak
        if is_title_fight:
            # Title fight win
            if fighter.previous_fight_was_title_win:
                # Previous fight was a title win - increment defense streak (defending)
                fighter.title_defense_streak += 1
            else:
                # Previous fight was NOT a title win - this is either:
                # 1. First title win, OR
                # 2. Champion returning to title defense after regular fight
                # Set to 1 (new title or new defense streak)
                fighter.title_defense_streak = 1
            fighter.previous_fight_was_title_win = True
        else:
            # Regular fight win - reset title defense streak to 0
            # (breaks consecutive title defense streak)
            # But keep previous_fight_was_title_win = True if they were already champion
            # (they're still champion, just didn't defend)
            fighter.title_defense_streak = 0
            # Note: previous_fight_was_title_win stays as is
            # If True: they're still champion, can defend next
            # If False: they weren't champion, still aren't
    else:
        fighter.losses += 1
        fighter.lose_streak += 1
        fighter.win_streak = 0
        fighter.title_defense_streak = 0
        fighter.previous_fight_was_title_win = False


def run_elo_calculation(
    elo_ready_path: str,
    output_path: str,
) -> Tuple[List[Dict[str, Any]], Dict[str, FighterElo]]:
    """
    Run ELO calculation on all fights chronologically.
    
    Args:
        elo_ready_path: Path to elo_ready.json
        output_path: Where to save results
        
    Returns:
        Tuple of (processed_fights, fighter_elos)
    """
    # Load fight data
    with open(elo_ready_path, "r") as f:
        data = json.load(f)
    
    fights = data["fights"]
    print(f"Loaded {len(fights)} fights")
    
    # Initialize fighter tracker
    fighters: Dict[str, FighterElo] = {}
    
    def get_or_create_fighter(fighter_id: str, name: str) -> FighterElo:
        if fighter_id not in fighters:
            fighters[fighter_id] = FighterElo(id=fighter_id, name=name)
        return fighters[fighter_id]
    
    # Process fights chronologically
    processed_fights: List[Dict[str, Any]] = []
    
    for i, fight in enumerate(fights):
        if i % 1000 == 0:
            print(f"  Processing fight {i}/{len(fights)}...")
        
        f1_id = fight["fighter1"]["id"]
        f1_name = fight["fighter1"]["name"]
        f2_id = fight["fighter2"]["id"]
        f2_name = fight["fighter2"]["name"]
        
        winner_id = fight["winner_id"]
        is_draw = fight["is_draw"]
        is_finish = fight["is_finish"]
        is_title = fight["is_title_fight"]
        
        # Get/create fighter records
        f1 = get_or_create_fighter(f1_id, f1_name)
        f2 = get_or_create_fighter(f2_id, f2_name)
        
        # Calculate ELO changes
        delta1, delta2, new_elo1, new_elo2 = process_fight(
            f1, f2, winner_id, is_draw, is_finish, is_title
        )
        
        # Build processed fight record
        processed = {
            "date": fight["date"],
            "event": fight["event"],
            "is_title_fight": is_title,
            "fighter1": {
                "id": f1_id,
                "name": f1_name,
                "elo_before": f1.elo,
                "elo_after": new_elo1,
                "elo_change": delta1,
                "ufc_record": [f1.wins, f1.losses],
                "win_streak": f1.win_streak,
            },
            "fighter2": {
                "id": f2_id,
                "name": f2_name,
                "elo_before": f2.elo,
                "elo_after": new_elo2,
                "elo_change": delta2,
                "ufc_record": [f2.wins, f2.losses],
                "win_streak": f2.win_streak,
            },
            "winner_id": winner_id,
            "is_draw": is_draw,
            "method": fight["method"],
            "is_finish": is_finish,
        }
        processed_fights.append(processed)
        
        # Update fighter records
        if is_draw:
            update_fighter_after_fight(f1, False, True, new_elo1, is_title)
            update_fighter_after_fight(f2, False, True, new_elo2, is_title)
        elif winner_id == f1_id:
            update_fighter_after_fight(f1, True, False, new_elo1, is_title)
            update_fighter_after_fight(f2, False, False, new_elo2, is_title)
        elif winner_id == f2_id:
            update_fighter_after_fight(f1, False, False, new_elo1, is_title)
            update_fighter_after_fight(f2, True, False, new_elo2, is_title)
        else:
            # No result - just update ELO without win/loss
            f1.elo = new_elo1
            f2.elo = new_elo2
    
    # Build output
    output = {
        "metadata": {
            "total_fights": len(processed_fights),
            "total_fighters": len(fighters),
            "constants": {
                "starting_elo": STARTING_ELO,
                "k_base": K_BASE,
                "m_finish_bonus": M_FINISH_KO_SUB,
                "m_title_fight": M_TITLE_FIGHT,
                "streak_coefficient": STREAK_COEFFICIENT,
                "streak_max": STREAK_MAX_MULTIPLIER,
            },
        },
        "fights": processed_fights,
        "rankings": _build_rankings(fighters),
    }
    
    # Save output
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"\nSaved ELO results to {output_path}")
    return processed_fights, fighters


def _build_rankings(fighters: Dict[str, FighterElo]) -> List[Dict[str, Any]]:
    """Build fighter rankings sorted by ELO."""
    rankings = []
    for fighter in fighters.values():
        rankings.append({
            "rank": 0,  # Will be set after sorting
            "id": fighter.id,
            "name": fighter.name,
            "elo": fighter.elo,
            "peak_elo": fighter.peak_elo,
            "record": f"{fighter.wins}-{fighter.losses}-{fighter.draws}",
            "wins": fighter.wins,
            "losses": fighter.losses,
            "draws": fighter.draws,
            "fights": fighter.fights,
            "win_streak": fighter.win_streak,
        })
    
    # Sort by ELO descending
    rankings.sort(key=lambda x: x["elo"], reverse=True)
    
    # Assign ranks
    for i, r in enumerate(rankings):
        r["rank"] = i + 1
    
    return rankings


def print_top_fighters(fighters: Dict[str, FighterElo], n: int = 20) -> None:
    """Print top N fighters by ELO."""
    sorted_fighters = sorted(
        fighters.values(), 
        key=lambda x: x.elo, 
        reverse=True
    )
    
    print(f"\n{'='*60}")
    print(f"TOP {n} FIGHTERS BY ELO")
    print(f"{'='*60}")
    print(f"{'Rank':<6}{'Name':<25}{'ELO':<10}{'Record':<12}{'Peak':<10}")
    print("-" * 60)
    
    for i, fighter in enumerate(sorted_fighters[:n]):
        record = f"{fighter.wins}-{fighter.losses}-{fighter.draws}"
        print(f"{i+1:<6}{fighter.name:<25}{fighter.elo:<10.1f}{record:<12}{fighter.peak_elo:<10.1f}")


def get_elo_distribution(fighters: Dict[str, FighterElo]) -> Dict[str, Any]:
    """Calculate ELO distribution statistics."""
    elos = [f.elo for f in fighters.values()]
    
    if not elos:
        return {}
    
    mean_elo = sum(elos) / len(elos)
    variance = sum((e - mean_elo) ** 2 for e in elos) / len(elos)
    std_dev = math.sqrt(variance)
    
    sorted_elos = sorted(elos)
    median = sorted_elos[len(elos) // 2]
    
    return {
        "count": len(elos),
        "mean": round(mean_elo, 1),
        "median": round(median, 1),
        "std_dev": round(std_dev, 1),
        "min": round(min(elos), 1),
        "max": round(max(elos), 1),
        "range_1200_1400": sum(1 for e in elos if 1200 <= e < 1400),
        "range_1400_1600": sum(1 for e in elos if 1400 <= e < 1600),
        "range_1600_1800": sum(1 for e in elos if 1600 <= e < 1800),
        "range_1800_plus": sum(1 for e in elos if e >= 1800),
    }

