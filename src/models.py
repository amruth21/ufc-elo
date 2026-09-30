from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class Fighter:
    id: str
    name: str
    record: str
    gender: str = ""  # "MALE" or "FEMALE"


@dataclass
class Fight:
    fighter1_id: str
    fighter2_id: str
    winner_id: str
    event_name: str
    date: str
    method: str
    is_title_fight: bool = False
    is_draw: bool = False


@dataclass
class FighterSnapshot:
    """Fighter stats at a specific point in time."""
    id: str
    name: str
    ufc_wins: int = 0
    ufc_losses: int = 0
    ufc_draws: int = 0
    win_streak: int = 0
    lose_streak: int = 0
    elo: float = 1500.0  # Starting ELO


@dataclass
class FightRecord:
    """Complete fight record for ELO calculation."""
    # Fight metadata
    date: str
    event_name: str
    is_title_fight: bool
    
    # Fighters
    fighter1_id: str
    fighter1_name: str
    fighter2_id: str
    fighter2_name: str
    
    # Outcome
    winner_id: str  # Empty string for draw
    is_draw: bool
    method: str  # "KO/TKO", "Submission", "Decision"
    is_finish: bool  # True for KO/TKO/Submission
    
    # Fighter 1 stats AT TIME OF FIGHT (before this fight)
    f1_ufc_wins: int = 0
    f1_ufc_losses: int = 0
    f1_win_streak: int = 0
    f1_lose_streak: int = 0
    f1_elo: float = 1500.0  # Starting ELO
    
    # Fighter 2 stats AT TIME OF FIGHT
    f2_ufc_wins: int = 0
    f2_ufc_losses: int = 0
    f2_win_streak: int = 0
    f2_lose_streak: int = 0
    f2_elo: float = 1500.0  # Starting ELO
    
    # ELO after fight (to be computed)
    f1_elo_after: Optional[float] = None
    f2_elo_after: Optional[float] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON export."""
        return {
            "date": self.date,
            "event": self.event_name,
            "is_title_fight": self.is_title_fight,
            "fighter1": {
                "id": self.fighter1_id,
                "name": self.fighter1_name,
                "ufc_record": [self.f1_ufc_wins, self.f1_ufc_losses],
                "win_streak": self.f1_win_streak,
                "lose_streak": self.f1_lose_streak,
                "elo": self.f1_elo,
                "elo_after": self.f1_elo_after,
            },
            "fighter2": {
                "id": self.fighter2_id,
                "name": self.fighter2_name,
                "ufc_record": [self.f2_ufc_wins, self.f2_ufc_losses],
                "win_streak": self.f2_win_streak,
                "lose_streak": self.f2_lose_streak,
                "elo": self.f2_elo,
                "elo_after": self.f2_elo_after,
            },
            "winner_id": self.winner_id,
            "is_draw": self.is_draw,
            "method": self.method,
            "is_finish": self.is_finish,
        }
