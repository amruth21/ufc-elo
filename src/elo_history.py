"""
ELO History Tracker - Track ELO progression over time for all fighters.

Creates data structures optimized for:
1. Getting top fighters at any point in time
2. Tracking individual fighter ELO history
3. Comparing fighters over time
"""
from __future__ import annotations

import csv
import json
import os
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple


STARTING_ELO = 1500.0


def build_elo_history(
    elo_ratings_path: str,
    output_dir: str,
) -> Dict[str, Any]:
    """
    Build ELO history data structures from elo_ratings.json.
    
    Creates:
    1. elo_timeline.json - Chronological events with top 10 at each point
    2. elo_by_fighter.json - Individual fighter ELO history
    3. elo_matrix.csv - Wide format CSV (dates x fighters)
    """
    # Load ELO ratings data
    with open(elo_ratings_path, "r") as f:
        data = json.load(f)
    
    fights = data["fights"]
    print(f"Processing {len(fights)} fights...")
    
    # Filter out future fights (only include fights before 2026-01-01)
    MAX_DATE = "2026-01-01"
    past_fights = []
    future_fights = 0
    for f in fights:
        fight_date = f.get("date", "")[:10]  # Extract YYYY-MM-DD
        if fight_date < MAX_DATE:
            past_fights.append(f)
        else:
            future_fights += 1
    
    if future_fights > 0:
        print(f"Filtered out {future_fights} future fights (after {MAX_DATE})")
    fights = past_fights
    print(f"Processing {len(fights)} fights (before {MAX_DATE})...")
    
    # Track current ELO for all fighters
    current_elos: Dict[str, float] = defaultdict(lambda: STARTING_ELO)
    fighter_names: Dict[str, str] = {}
    
    # Build history structures
    timeline: List[Dict[str, Any]] = []
    fighter_history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    
    # Track all unique event dates
    events_seen: Set[str] = set()
    
    for i, fight in enumerate(fights):
        if i % 1000 == 0:
            print(f"  Processing fight {i}/{len(fights)}...")
        
        date = fight["date"]
        event = fight["event"]
        
        f1_id = fight["fighter1"]["id"]
        f1_name = fight["fighter1"]["name"]
        f1_elo_before = fight["fighter1"]["elo_before"]
        f1_elo_after = fight["fighter1"]["elo_after"]
        f1_elo_change = fight["fighter1"]["elo_change"]
        
        f2_id = fight["fighter2"]["id"]
        f2_name = fight["fighter2"]["name"]
        f2_elo_before = fight["fighter2"]["elo_before"]
        f2_elo_after = fight["fighter2"]["elo_after"]
        f2_elo_change = fight["fighter2"]["elo_change"]
        
        # Store names
        fighter_names[f1_id] = f1_name
        fighter_names[f2_id] = f2_name
        
        # Update current ELOs
        current_elos[f1_id] = f1_elo_after
        current_elos[f2_id] = f2_elo_after
        
        # Extract fight details
        method = fight.get("method", "")
        is_finish = fight.get("is_finish", False)
        is_title_fight = fight.get("is_title_fight", False)
        
        # Add to fighter history with enhanced details
        fighter_history[f1_id].append({
            "date": date,
            "event": event,
            "elo_before": f1_elo_before,
            "elo_after": f1_elo_after,
            "elo_change": f1_elo_change,
            "opponent_id": f2_id,
            "opponent_name": f2_name,
            "opponent_elo_before": f2_elo_before,
            "result": "W" if fight["winner_id"] == f1_id else ("D" if fight["is_draw"] else "L"),
            "method": method,
            "is_finish": is_finish,
            "is_title_fight": is_title_fight,
        })
        fighter_history[f2_id].append({
            "date": date,
            "event": event,
            "elo_before": f2_elo_before,
            "elo_after": f2_elo_after,
            "elo_change": f2_elo_change,
            "opponent_id": f1_id,
            "opponent_name": f1_name,
            "opponent_elo_before": f1_elo_before,
            "result": "W" if fight["winner_id"] == f2_id else ("D" if fight["is_draw"] else "L"),
            "method": method,
            "is_finish": is_finish,
            "is_title_fight": is_title_fight,
        })
        
        # Create unique event key
        event_key = f"{date}_{event}"
        
        # Only add timeline entry once per event
        if event_key not in events_seen:
            events_seen.add(event_key)
            
            # Get current top 10
            top_10 = _get_top_n(current_elos, fighter_names, 10)
            
            timeline.append({
                "date": date,
                "event": event,
                "fight_number": i + 1,
                "top_10": top_10,
            })
    
    # Build final fighter history with metadata
    fighter_history_full: Dict[str, Dict[str, Any]] = {}
    for fid, history in fighter_history.items():
        # Calculate peak ELO and best/worst performances
        peak_elo = max(h["elo_after"] for h in history) if history else STARTING_ELO
        best_gain = max((h for h in history if h["elo_change"] > 0), key=lambda x: x["elo_change"], default=None)
        worst_loss = min((h for h in history if h["elo_change"] < 0), key=lambda x: x["elo_change"], default=None)
        
        fighter_history_full[fid] = {
            "id": fid,
            "name": fighter_names.get(fid, "Unknown"),
            "current_elo": current_elos[fid],
            "peak_elo": peak_elo,
            "fights": len(history),
            "best_gain": best_gain,
            "worst_loss": worst_loss,
            "history": history,
        }
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Save timeline
    timeline_path = os.path.join(output_dir, "elo_timeline.json")
    timeline_output = {
        "metadata": {
            "total_events": len(timeline),
            "total_fighters": len(fighter_names),
            "date_range": [timeline[0]["date"][:10], timeline[-1]["date"][:10]] if timeline else [],
        },
        "timeline": timeline,
    }
    with open(timeline_path, "w") as f:
        json.dump(timeline_output, f, indent=2)
    print(f"Saved timeline to {timeline_path}")
    
    # Save fighter history
    history_path = os.path.join(output_dir, "elo_by_fighter.json")
    with open(history_path, "w") as f:
        json.dump(fighter_history_full, f, indent=2)
    print(f"Saved fighter history to {history_path}")
    
    # Build and save ELO matrix CSV
    matrix_path = os.path.join(output_dir, "elo_matrix.csv")
    _build_elo_matrix_csv(fights, fighter_names, matrix_path)
    print(f"Saved ELO matrix to {matrix_path}")
    
    # Save current rankings
    rankings_path = os.path.join(output_dir, "current_rankings.csv")
    _save_current_rankings(current_elos, fighter_names, rankings_path)
    print(f"Saved current rankings to {rankings_path}")
    
    return {
        "timeline": timeline,
        "fighter_history": fighter_history_full,
    }


def _get_top_n(
    current_elos: Dict[str, float],
    fighter_names: Dict[str, str],
    n: int = 10,
) -> List[Dict[str, Any]]:
    """Get top N fighters by current ELO."""
    sorted_fighters = sorted(
        current_elos.items(),
        key=lambda x: x[1],
        reverse=True
    )[:n]
    
    return [
        {
            "rank": i + 1,
            "id": fid,
            "name": fighter_names.get(fid, "Unknown"),
            "elo": round(elo, 1),
        }
        for i, (fid, elo) in enumerate(sorted_fighters)
    ]


def _build_elo_matrix_csv(
    fights: List[Dict[str, Any]],
    fighter_names: Dict[str, str],
    output_path: str,
) -> None:
    """
    Build a CSV matrix where:
    - Rows = events (chronological)
    - Columns = fighters
    - Values = ELO after that event
    """
    # Track ELOs over time
    current_elos: Dict[str, float] = defaultdict(lambda: STARTING_ELO)
    
    # Get all unique fighters
    all_fighters = set()
    for fight in fights:
        all_fighters.add(fight["fighter1"]["id"])
        all_fighters.add(fight["fighter2"]["id"])
    
    # Sort fighters by name for consistent column order
    sorted_fighters = sorted(all_fighters, key=lambda x: fighter_names.get(x, ""))
    
    # Build rows
    rows: List[Dict[str, Any]] = []
    seen_events: Set[str] = set()
    
    for fight in fights:
        date = fight["date"][:10]
        event = fight["event"]
        
        f1_id = fight["fighter1"]["id"]
        f2_id = fight["fighter2"]["id"]
        
        # Update ELOs
        current_elos[f1_id] = fight["fighter1"]["elo_after"]
        current_elos[f2_id] = fight["fighter2"]["elo_after"]
        
        # Add row for this event (only once per event)
        event_key = f"{date}_{event}"
        if event_key not in seen_events:
            seen_events.add(event_key)
            
            row = {
                "date": date,
                "event": event,
            }
            # Add all fighter ELOs
            for fid in sorted_fighters:
                name = fighter_names.get(fid, fid)
                row[name] = round(current_elos[fid], 1)
            
            rows.append(row)
    
    # Write CSV
    if rows:
        fieldnames = ["date", "event"] + [fighter_names.get(fid, fid) for fid in sorted_fighters]
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)


def _save_current_rankings(
    current_elos: Dict[str, float],
    fighter_names: Dict[str, str],
    output_path: str,
) -> None:
    """Save current rankings to CSV."""
    sorted_fighters = sorted(
        current_elos.items(),
        key=lambda x: x[1],
        reverse=True
    )
    
    rows = []
    for i, (fid, elo) in enumerate(sorted_fighters):
        rows.append({
            "rank": i + 1,
            "id": fid,
            "name": fighter_names.get(fid, "Unknown"),
            "elo": round(elo, 1),
        })
    
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["rank", "id", "name", "elo"])
        writer.writeheader()
        writer.writerows(rows)


def get_top_fighters_at_date(
    timeline_path: str,
    target_date: str,
) -> List[Dict[str, Any]]:
    """
    Get top fighters at a specific date (max 10 from timeline).
    
    Args:
        timeline_path: Path to elo_timeline.json
        target_date: Date in YYYY-MM-DD format
        
    Returns:
        List of top 10 fighters at that date
    """
    with open(timeline_path, "r") as f:
        data = json.load(f)
    
    timeline = data["timeline"]
    
    # Find the most recent event before or on target_date
    result = None
    for entry in timeline:
        event_date = entry["date"][:10]
        if event_date <= target_date:
            result = entry
        else:
            break
    
    if result:
        return result["top_10"]
    return []


def get_top_fighters_at_date_full(
    history_path: str,
    target_date: str,
    top_n: int = 10,
) -> List[Dict[str, Any]]:
    """
    Get top N fighters at a specific date (any number).
    
    Args:
        history_path: Path to elo_by_fighter.json
        target_date: Date in YYYY-MM-DD format
        top_n: Number of top fighters to return
        
    Returns:
        List of top N fighters at that date
    """
    with open(history_path, "r") as f:
        fighters_data = json.load(f)
    
    # Calculate ELO at target date for each fighter
    fighter_elos = []
    
    for fid, fdata in fighters_data.items():
        # Start with default ELO
        elo = STARTING_ELO
        
        # Find ELO at or before target date
        for entry in fdata["history"]:
            entry_date = entry["date"][:10]
            if entry_date <= target_date:
                elo = entry["elo_after"]
            else:
                break
        
        # Only include fighters who had fought by this date
        first_fight_date = fdata["history"][0]["date"][:10] if fdata["history"] else None
        if first_fight_date and first_fight_date <= target_date:
            fighter_elos.append({
                "id": fid,
                "name": fdata["name"],
                "elo": elo,
            })
    
    # Sort by ELO descending
    fighter_elos.sort(key=lambda x: x["elo"], reverse=True)
    
    # Add ranks and return top N
    result = []
    for i, fighter in enumerate(fighter_elos[:top_n]):
        result.append({
            "rank": i + 1,
            "id": fighter["id"],
            "name": fighter["name"],
            "elo": round(fighter["elo"], 1),
        })
    
    return result


def get_fighter_history(
    history_path: str,
    fighter_name: str,
) -> Optional[Dict[str, Any]]:
    """
    Get a fighter's ELO history by name.
    
    Args:
        history_path: Path to elo_by_fighter.json
        fighter_name: Fighter name (case-insensitive partial match)
        
    Returns:
        Fighter history dict or None if not found
    """
    with open(history_path, "r") as f:
        data = json.load(f)
    
    fighter_name_lower = fighter_name.lower()
    
    for fid, fighter_data in data.items():
        if fighter_name_lower in fighter_data["name"].lower():
            return fighter_data
    
    return None


def compare_fighters_over_time(
    history_path: str,
    fighter_names: List[str],
) -> Dict[str, List[Tuple[str, float]]]:
    """
    Get ELO history for multiple fighters for comparison.
    
    Returns dict of {fighter_name: [(date, elo), ...]}
    """
    with open(history_path, "r") as f:
        data = json.load(f)
    
    result = {}
    
    for target_name in fighter_names:
        target_lower = target_name.lower()
        for fid, fighter_data in data.items():
            if target_lower in fighter_data["name"].lower():
                history = [(h["date"][:10], h["elo_after"]) for h in fighter_data["history"]]
                result[fighter_data["name"]] = history
                break
    
    return result


def get_largest_elo_gains(
    history_path: str,
    top_n: int = 20,
) -> List[Dict[str, Any]]:
    """
    Get the largest ELO gains from single fights.
    
    Returns list of fights sorted by ELO gain (descending).
    """
    with open(history_path, "r") as f:
        data = json.load(f)
    
    all_gains = []
    
    for fid, fighter_data in data.items():
        for fight in fighter_data["history"]:
            if fight["elo_change"] > 0:  # Only wins
                all_gains.append({
                    "fighter_id": fid,
                    "fighter_name": fighter_data["name"],
                    "date": fight["date"],
                    "event": fight["event"],
                    "opponent_name": fight["opponent_name"],
                    "opponent_elo": fight["opponent_elo_before"],
                    "elo_before": fight["elo_before"],
                    "elo_after": fight["elo_after"],
                    "elo_change": fight["elo_change"],
                    "method": fight["method"],
                    "is_finish": fight["is_finish"],
                    "is_title_fight": fight["is_title_fight"],
                    "result": fight["result"],
                })
    
    # Sort by ELO change descending
    all_gains.sort(key=lambda x: x["elo_change"], reverse=True)
    
    return all_gains[:top_n]


def get_largest_elo_losses(
    history_path: str,
    top_n: int = 20,
) -> List[Dict[str, Any]]:
    """
    Get the largest ELO losses (most punishing losses) from single fights.
    
    Returns list of fights sorted by ELO loss (ascending, most negative first).
    """
    with open(history_path, "r") as f:
        data = json.load(f)
    
    all_losses = []
    
    for fid, fighter_data in data.items():
        for fight in fighter_data["history"]:
            if fight["elo_change"] < 0:  # Only losses
                all_losses.append({
                    "fighter_id": fid,
                    "fighter_name": fighter_data["name"],
                    "date": fight["date"],
                    "event": fight["event"],
                    "opponent_name": fight["opponent_name"],
                    "opponent_elo": fight["opponent_elo_before"],
                    "elo_before": fight["elo_before"],
                    "elo_after": fight["elo_after"],
                    "elo_change": fight["elo_change"],
                    "method": fight["method"],
                    "is_finish": fight["is_finish"],
                    "is_title_fight": fight["is_title_fight"],
                    "result": fight["result"],
                })
    
    # Sort by ELO change ascending (most negative first)
    all_losses.sort(key=lambda x: x["elo_change"])
    
    return all_losses[:top_n]


def get_all_time_peaks(
    history_path: str,
    top_n: int = 50,
) -> List[Dict[str, Any]]:
    """
    Get all-time peak ELOs achieved by fighters.
    
    Returns list sorted by peak ELO (descending).
    """
    with open(history_path, "r") as f:
        data = json.load(f)
    
    peaks = []
    
    for fid, fighter_data in data.items():
        if fighter_data.get("peak_elo"):
            peaks.append({
                "fighter_id": fid,
                "fighter_name": fighter_data["name"],
                "peak_elo": fighter_data["peak_elo"],
                "current_elo": fighter_data.get("current_elo", STARTING_ELO),
                "fights": fighter_data.get("fights", 0),
            })
    
    # Sort by peak ELO descending
    peaks.sort(key=lambda x: x["peak_elo"], reverse=True)
    
    return peaks[:top_n]


def get_fighter_analysis(
    history_path: str,
    fighter_name: str,
) -> Optional[Dict[str, Any]]:
    """
    Get comprehensive analysis for a specific fighter.
    
    Returns fighter stats including biggest gains/losses.
    """
    fighter_data = get_fighter_history(history_path, fighter_name)
    
    if not fighter_data:
        return None
    
    # Extract best and worst performances
    best_gain = fighter_data.get("best_gain")
    worst_loss = fighter_data.get("worst_loss")
    
    # Calculate additional stats
    wins = sum(1 for h in fighter_data["history"] if h["result"] == "W")
    losses = sum(1 for h in fighter_data["history"] if h["result"] == "L")
    draws = sum(1 for h in fighter_data["history"] if h["result"] == "D")
    
    title_fights = sum(1 for h in fighter_data["history"] if h.get("is_title_fight", False))
    finishes = sum(1 for h in fighter_data["history"] if h.get("is_finish", False) and h["result"] == "W")
    
    return {
        "id": fighter_data["id"],
        "name": fighter_data["name"],
        "current_elo": fighter_data["current_elo"],
        "peak_elo": fighter_data["peak_elo"],
        "record": f"{wins}-{losses}-{draws}",
        "total_fights": fighter_data["fights"],
        "title_fights": title_fights,
        "finishes": finishes,
        "best_gain": best_gain,
        "worst_loss": worst_loss,
        "history": fighter_data["history"],
    }

