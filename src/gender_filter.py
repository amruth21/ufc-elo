"""Filter fighters and fights by gender."""
from __future__ import annotations

import json
import os
from typing import Dict, List, Set, Tuple

from .espn_api import ESPNApiClient


def load_fighter_genders(
    api: ESPNApiClient,
    fighter_ids: List[str],
    cache_file: str = "data/fighter_genders.json",
) -> Dict[str, str]:
    """
    Load or fetch gender for all fighters.
    Returns dict of {fighter_id: "MALE" or "FEMALE"}
    """
    # Load from cache if exists
    gender_cache: Dict[str, str] = {}
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            gender_cache = json.load(f)
    
    # Fetch missing genders
    missing = [fid for fid in fighter_ids if fid not in gender_cache]
    if missing:
        print(f"Fetching gender for {len(missing)} fighters...")
        for i, fid in enumerate(missing):
            if i % 50 == 0:
                print(f"  {i}/{len(missing)}...")
            try:
                detail = api.get_athlete_detail(fid)
                gender = detail.get("gender", "UNKNOWN")
                gender_cache[fid] = gender
            except Exception as e:
                gender_cache[fid] = "UNKNOWN"
        
        # Save updated cache
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        with open(cache_file, "w") as f:
            json.dump(gender_cache, f, indent=2)
        print(f"Saved gender cache to {cache_file}")
    
    return gender_cache


def filter_male_fighters(
    fighter_ids: List[str],
    gender_cache: Dict[str, str],
) -> Set[str]:
    """Return set of male fighter IDs."""
    return {fid for fid in fighter_ids if gender_cache.get(fid) == "MALE"}


def filter_male_fights(
    fights: List[dict],
    male_fighter_ids: Set[str],
) -> List[dict]:
    """
    Filter fights to only include those where BOTH fighters are male.
    
    Args:
        fights: List of fight dicts with 'source' and 'target' keys
        male_fighter_ids: Set of male fighter IDs
        
    Returns:
        List of fights where both participants are male
    """
    filtered = []
    for fight in fights:
        f1 = fight.get("source") or fight.get("fighter1_id")
        f2 = fight.get("target") or fight.get("fighter2_id")
        if f1 in male_fighter_ids and f2 in male_fighter_ids:
            filtered.append(fight)
    return filtered


def get_gender_stats(gender_cache: Dict[str, str]) -> Dict[str, int]:
    """Return count of fighters by gender."""
    stats = {"MALE": 0, "FEMALE": 0, "UNKNOWN": 0}
    for gender in gender_cache.values():
        if gender in stats:
            stats[gender] += 1
        else:
            stats["UNKNOWN"] += 1
    return stats

