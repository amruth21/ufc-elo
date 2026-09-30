"""Build chronological fight list with fighter stats at time of each fight."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .models import FightRecord, FighterSnapshot


@dataclass
class FighterState:
    """Mutable state tracking for a fighter during chronological processing."""
    id: str
    name: str
    ufc_wins: int = 0
    ufc_losses: int = 0
    ufc_draws: int = 0
    win_streak: int = 0
    lose_streak: int = 0
    elo: float = 1500.0  # Starting ELO
    
    def snapshot(self) -> FighterSnapshot:
        """Return immutable snapshot of current state."""
        return FighterSnapshot(
            id=self.id,
            name=self.name,
            ufc_wins=self.ufc_wins,
            ufc_losses=self.ufc_losses,
            ufc_draws=self.ufc_draws,
            win_streak=self.win_streak,
            lose_streak=self.lose_streak,
            elo=self.elo,
        )
    
    def record_win(self) -> None:
        """Update state after a win."""
        self.ufc_wins += 1
        self.win_streak += 1
        self.lose_streak = 0
    
    def record_loss(self) -> None:
        """Update state after a loss."""
        self.ufc_losses += 1
        self.lose_streak += 1
        self.win_streak = 0
    
    def record_draw(self) -> None:
        """Update state after a draw."""
        self.ufc_draws += 1
        # Draws reset both streaks
        self.win_streak = 0
        self.lose_streak = 0


def build_elo_ready_data(
    enhanced_fights_path: str,
    male_fighter_ids: Set[str],
    fighter_names: Dict[str, str],
    output_path: str,
) -> List[FightRecord]:
    """
    Build chronological fight list with fighter stats at time of each fight.
    
    Args:
        enhanced_fights_path: Path to enhanced fights JSON
        male_fighter_ids: Set of male fighter IDs (for filtering)
        fighter_names: Dict of fighter_id -> name
        output_path: Where to save the elo_ready.json
        
    Returns:
        List of FightRecord objects sorted chronologically
    """
    # Load enhanced fights
    with open(enhanced_fights_path, "r") as f:
        fights_data = json.load(f)
    
    print(f"Loaded {len(fights_data)} fights")
    
    # Filter out future fights (only include fights before 2026-01-01)
    MAX_DATE = "2026-01-01"
    past_fights = []
    future_fights = 0
    for f in fights_data:
        fight_date = f.get("date", "")[:10]  # Extract YYYY-MM-DD
        if fight_date < MAX_DATE:
            past_fights.append(f)
        else:
            future_fights += 1
    
    if future_fights > 0:
        print(f"Filtered out {future_fights} future fights (after {MAX_DATE})")
    
    # Filter to male-only fights
    male_fights = [
        f for f in past_fights
        if f["fighter1_id"] in male_fighter_ids and f["fighter2_id"] in male_fighter_ids
    ]
    print(f"Filtered to {len(male_fights)} male-only fights (before {MAX_DATE})")
    
    # Sort by date (already sorted, but ensure)
    male_fights.sort(key=lambda x: x["date"])
    
    # Initialize fighter states (lazy - create when first seen)
    fighter_states: Dict[str, FighterState] = {}
    
    def get_or_create_state(fighter_id: str) -> FighterState:
        if fighter_id not in fighter_states:
            fighter_states[fighter_id] = FighterState(
                id=fighter_id,
                name=fighter_names.get(fighter_id, "Unknown"),
            )
        return fighter_states[fighter_id]
    
    # Process fights chronologically
    fight_records: List[FightRecord] = []
    
    for i, fight in enumerate(male_fights):
        if i % 500 == 0:
            print(f"  Processing fight {i}/{len(male_fights)}...")
        
        f1_id = fight["fighter1_id"]
        f2_id = fight["fighter2_id"]
        winner_id = fight["winner_id"]
        is_draw = fight.get("is_draw", False)
        
        # Get current states (before this fight)
        f1_state = get_or_create_state(f1_id)
        f2_state = get_or_create_state(f2_id)
        
        # Determine method category
        method = fight.get("method", "")
        method_cat = fight.get("method_category", "Decision")
        is_finish = method_cat in ["KO/TKO", "Submission"]
        
        # Create fight record with stats AT TIME OF FIGHT
        record = FightRecord(
            date=fight["date"],
            event_name=fight.get("event_name", ""),
            is_title_fight=fight.get("is_title_fight", False),
            fighter1_id=f1_id,
            fighter1_name=f1_state.name,
            fighter2_id=f2_id,
            fighter2_name=f2_state.name,
            winner_id=winner_id,
            is_draw=is_draw,
            method=method,
            is_finish=is_finish,
            # Fighter 1 stats at time of fight
            f1_ufc_wins=f1_state.ufc_wins,
            f1_ufc_losses=f1_state.ufc_losses,
            f1_win_streak=f1_state.win_streak,
            f1_lose_streak=f1_state.lose_streak,
            f1_elo=f1_state.elo,
            # Fighter 2 stats at time of fight
            f2_ufc_wins=f2_state.ufc_wins,
            f2_ufc_losses=f2_state.ufc_losses,
            f2_win_streak=f2_state.win_streak,
            f2_lose_streak=f2_state.lose_streak,
            f2_elo=f2_state.elo,
        )
        fight_records.append(record)
        
        # Update fighter states AFTER recording the fight
        if is_draw:
            f1_state.record_draw()
            f2_state.record_draw()
        elif winner_id == f1_id:
            f1_state.record_win()
            f2_state.record_loss()
        elif winner_id == f2_id:
            f1_state.record_loss()
            f2_state.record_win()
        else:
            # No winner recorded - treat as draw
            f1_state.record_draw()
            f2_state.record_draw()
    
    # Build output data
    output = {
        "metadata": {
            "total_fights": len(fight_records),
            "date_range": [
                fight_records[0].date[:10] if fight_records else "",
                fight_records[-1].date[:10] if fight_records else "",
            ],
            "fighters_count": len(fighter_states),
            "note": "ELO values are placeholders (500.0). Apply your ELO algorithm to compute actual values.",
        },
        "fights": [r.to_dict() for r in fight_records],
    }
    
    # Save to output
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"\nSaved ELO-ready data to {output_path}")
    print(f"  Total fights: {len(fight_records)}")
    print(f"  Date range: {output['metadata']['date_range']}")
    print(f"  Unique fighters: {len(fighter_states)}")
    
    return fight_records


def get_final_fighter_stats(
    fight_records: List[FightRecord],
    fighter_names: Dict[str, str],
) -> Dict[str, FighterState]:
    """
    Process all fights and return final fighter states.
    Useful for getting current records/stats.
    """
    fighter_states: Dict[str, FighterState] = {}
    
    def get_or_create_state(fighter_id: str) -> FighterState:
        if fighter_id not in fighter_states:
            fighter_states[fighter_id] = FighterState(
                id=fighter_id,
                name=fighter_names.get(fighter_id, "Unknown"),
            )
        return fighter_states[fighter_id]
    
    for record in fight_records:
        f1_state = get_or_create_state(record.fighter1_id)
        f2_state = get_or_create_state(record.fighter2_id)
        
        if record.is_draw:
            f1_state.record_draw()
            f2_state.record_draw()
        elif record.winner_id == record.fighter1_id:
            f1_state.record_win()
            f2_state.record_loss()
        elif record.winner_id == record.fighter2_id:
            f1_state.record_loss()
            f2_state.record_win()
        else:
            f1_state.record_draw()
            f2_state.record_draw()
    
    return fighter_states

