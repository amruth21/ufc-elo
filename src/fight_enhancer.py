"""Enhance fight data with event name, method, and title fight detection."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Set, Tuple

from .espn_api import ESPNApiClient
from .models import Fight


def enhance_fights_from_graph(
    api: ESPNApiClient,
    fight_graph_path: str,
    fighters_csv_path: str,
    output_path: str,
) -> List[Dict[str, Any]]:
    """
    Re-process fight data to add event name, method, and title fight status.
    
    Returns list of enhanced fight dicts.
    """
    # Load existing fight graph
    with open(fight_graph_path, "r") as f:
        graph_data = json.load(f)
    
    # Load fighter names
    fighter_names = {}
    with open(fighters_csv_path, "r") as f:
        for line in f:
            if line.startswith("id"):
                continue
            parts = line.strip().split(",")
            if len(parts) >= 2:
                fighter_names[parts[0]] = parts[1]
    
    # Get all unique fighter IDs
    fighter_ids = set()
    for edge in graph_data["edges"]:
        fighter_ids.add(edge["source"])
        fighter_ids.add(edge["target"])
    
    print(f"Processing fights for {len(fighter_ids)} fighters...")
    
    # Process each fighter's eventlog to get full fight details
    enhanced_fights: Dict[str, Dict[str, Any]] = {}  # key = (f1_id, f2_id, date)
    
    processed = 0
    for fighter_id in fighter_ids:
        processed += 1
        if processed % 50 == 0:
            print(f"  Processed {processed}/{len(fighter_ids)} fighters...")
        
        try:
            eventlog = api.get_athlete_eventlog(fighter_id)
            events = eventlog.get("events", {}).get("items", [])
            
            for event_item in events:
                fight_data = _process_event_item(api, fighter_id, event_item, fighter_names)
                if fight_data is None:
                    continue
                
                # Create unique key (sorted fighter IDs + date)
                f1, f2 = sorted([fight_data["fighter1_id"], fight_data["fighter2_id"]])
                date = fight_data["date"]
                key = f"{f1}_{f2}_{date}"
                
                # Only add if not already processed
                if key not in enhanced_fights:
                    enhanced_fights[key] = fight_data
                    
        except Exception as e:
            print(f"  Error processing fighter {fighter_id}: {e}")
            continue
    
    # Convert to list and sort by date
    fights_list = list(enhanced_fights.values())
    
    # Filter out future fights (only include fights before 2026-01-01)
    MAX_DATE = "2026-01-01"
    past_fights = []
    future_fights = 0
    for f in fights_list:
        fight_date = f.get("date", "")[:10]  # Extract YYYY-MM-DD
        if fight_date < MAX_DATE:
            past_fights.append(f)
        else:
            future_fights += 1
    
    if future_fights > 0:
        print(f"Filtered out {future_fights} future fights (after {MAX_DATE})")
    
    past_fights.sort(key=lambda x: x["date"])
    
    # Save to output
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(past_fights, f, indent=2)
    
    print(f"Saved {len(past_fights)} enhanced fights to {output_path} (before {MAX_DATE})")
    return past_fights


def _process_event_item(
    api: ESPNApiClient,
    fighter_id: str,
    event_item: Dict[str, Any],
    fighter_names: Dict[str, str],
) -> Optional[Dict[str, Any]]:
    """Process a single event item and return enhanced fight data."""
    event_ref = event_item.get("event", {}).get("$ref", "")
    competition_ref = event_item.get("competition", {}).get("$ref", "")
    
    # Filter: Only process UFC fights
    if "/leagues/ufc/" not in event_ref:
        return None
    
    try:
        # Get event details (name)
        event_detail = api.get_event_detail(event_ref)
        event_name = event_detail.get("name", "")
        
        # Get competition details
        competition_detail = api.get_competition_detail(competition_ref)
        competitors = competition_detail.get("competitors", [])
        date = competition_detail.get("date", "")
        description = competition_detail.get("description", "")
        
        # Detect title fight (5 rounds = title fight)
        is_title_fight = "5 Rnd" in description or "Championship" in event_name.lower()
        
        # Find opponent and winner
        opponent_id = None
        winner_id = None
        is_draw = True  # Assume draw unless we find a winner
        
        for comp in competitors:
            comp_id = str(comp.get("id", ""))
            is_winner = comp.get("winner", False)
            
            if comp_id == str(fighter_id):
                if is_winner:
                    winner_id = fighter_id
                    is_draw = False
            else:
                opponent_id = comp_id
                if is_winner:
                    winner_id = comp_id
                    is_draw = False
        
        if not opponent_id:
            return None
        
        # Get fight result/method from status
        method = ""
        method_category = "Decision"  # Default
        try:
            status = api.get_competition_status(competition_ref)
            result = status.get("result", {})
            method = result.get("displayName", "")
            
            # Categorize method
            method_lower = method.lower()
            if "ko" in method_lower or "tko" in method_lower:
                method_category = "KO/TKO"
            elif "sub" in method_lower:
                method_category = "Submission"
            elif "dec" in method_lower:
                method_category = "Decision"
            elif "draw" in method_lower or "nc" in method_lower:
                method_category = "Draw/NC"
                is_draw = True
                winner_id = ""
        except Exception:
            pass
        
        is_finish = method_category in ["KO/TKO", "Submission"]
        
        return {
            "date": date,
            "event_name": event_name,
            "is_title_fight": is_title_fight,
            "fighter1_id": str(fighter_id),
            "fighter1_name": fighter_names.get(str(fighter_id), ""),
            "fighter2_id": str(opponent_id),
            "fighter2_name": fighter_names.get(str(opponent_id), ""),
            "winner_id": str(winner_id) if winner_id else "",
            "is_draw": is_draw,
            "method": method,
            "method_category": method_category,
            "is_finish": is_finish,
        }
        
    except Exception as e:
        return None


def classify_method(method: str) -> Tuple[str, bool]:
    """
    Classify fight method into category and whether it's a finish.
    
    Returns: (category, is_finish)
    """
    method_lower = method.lower()
    
    if "ko" in method_lower or "tko" in method_lower:
        return "KO/TKO", True
    elif "sub" in method_lower:
        return "Submission", True
    elif "dec" in method_lower:
        return "Decision", False
    elif "draw" in method_lower:
        return "Draw", False
    elif "nc" in method_lower or "no contest" in method_lower:
        return "No Contest", False
    else:
        return "Decision", False  # Default to decision

