from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import quote

import networkx as nx
import requests

from .espn_api import ESPNApiClient
from .models import Fight, Fighter

SEARCH_URL = "https://site.web.api.espn.com/apis/common/v3/search"


def build_fighter_graph(
    api: ESPNApiClient,
    seed_fighters: List[Tuple[str, str]],
    skip_bfs: bool = True,
    max_depth: int = 0,
    max_fighters: int = 0,
) -> Tuple[nx.MultiGraph, Dict[str, Fighter]]:
    """
    Build a graph of UFC fighters using BFS traversal.
    Uses MultiGraph to support rematches (multiple fights between same pair).
    """
    graph: nx.MultiGraph = nx.MultiGraph()  # Supports multiple edges (rematches)
    fighters: Dict[str, Fighter] = {}
    visited: Set[str] = set()
    queue: deque[Tuple[str, int]] = deque()
    # Track fights we've already added (frozenset of fighter IDs + date)
    seen_fights: Set[Tuple[frozenset, str]] = set()

    for fighter_id, _ in seed_fighters:
        if fighter_id not in visited:
            queue.append((fighter_id, 0))

    total_seeds = len(queue)
    processed = 0

    while queue:
        if max_fighters > 0 and processed >= max_fighters:
            print(f"Reached max fighters limit ({max_fighters})")
            break
            
        fighter_id, depth = queue.popleft()
        if fighter_id in visited:
            continue
        visited.add(fighter_id)
        processed += 1

        if processed % 10 == 0 or processed <= 5:
            print(f"Processing fighter {processed} (depth {depth}, queue: {len(queue)})...")

        try:
            detail = api.get_athlete_detail(fighter_id)
            fighter = Fighter(
                id=str(fighter_id),
                name=detail.get("displayName") or detail.get("fullName") or "",
                record="",
            )
            fighters[fighter.id] = fighter
            graph.add_node(fighter.id, name=fighter.name)
        except Exception as e:
            print(f"  Error fetching fighter {fighter_id}: {e}")
            continue

        try:
            eventlog = api.get_athlete_eventlog(fighter_id)
            events = eventlog.get("events", {}).get("items", [])
        except Exception as e:
            print(f"  Error fetching eventlog for {fighter_id}: {e}")
            continue

        for event_item in events:
            fight = _process_event_item_fast(api, fighter_id, event_item)
            if fight is None:
                continue
            
            # Create unique fight key (pair of fighters + date)
            fight_key = (frozenset([fight.fighter1_id, fight.fighter2_id]), fight.date)
            if fight_key in seen_fights:
                continue  # Skip duplicate fight
            seen_fights.add(fight_key)
            
            if fight.fighter2_id not in graph:
                graph.add_node(fight.fighter2_id)
            
            if not skip_bfs and fight.fighter2_id not in visited:
                next_depth = depth + 1
                if max_depth == 0 or next_depth <= max_depth:
                    if fight.fighter2_id not in [q[0] for q in queue]:
                        queue.append((fight.fighter2_id, next_depth))

            graph.add_edge(
                fight.fighter1_id,
                fight.fighter2_id,
                winner_id=fight.winner_id,
                event_name=fight.event_name,
                date=fight.date,
                method=fight.method,
            )

    print(f"Processed {processed} fighters, found {graph.number_of_edges()} UFC fights")
    return graph, fighters


def find_fighters_by_name(
    api: ESPNApiClient,
    names: List[str],
    all_athletes: List[Tuple[str, str]],
) -> List[Tuple[str, str]]:
    """
    Find athlete IDs for given fighter names using ESPN search API.
    """
    found: List[Tuple[str, str]] = []
    not_found: List[str] = []
    
    print(f"Looking up {len(names)} fighter names via ESPN search...")
    
    for i, name in enumerate(names):
        if i % 20 == 0:
            print(f"  Searched {i}/{len(names)} names...")
        
        athlete_id = _search_fighter_by_name(name)
        if athlete_id:
            found.append((athlete_id, name))
        else:
            not_found.append(name)
    
    if not_found:
        print(f"Could not find ({len(not_found)}): {not_found[:5]}{'...' if len(not_found) > 5 else ''}")
    
    print(f"Found {len(found)}/{len(names)} requested fighters")
    return found


def _search_fighter_by_name(name: str) -> Optional[str]:
    """Search ESPN for a fighter by name and return their athlete ID."""
    try:
        import time
        time.sleep(0.15)  # Rate limit
        
        params = {
            "query": name,
            "limit": 5,
            "type": "player",
        }
        response = requests.get(SEARCH_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        items = data.get("items", [])
        for item in items:
            # Must be MMA fighter
            if item.get("sport") == "mma":
                return str(item.get("id"))
        
        return None
    except Exception:
        return None


def _normalize_name(name: str) -> str:
    """Normalize name for matching."""
    import unicodedata
    normalized = unicodedata.normalize('NFD', name.lower())
    return ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')


def _process_event_item_fast(
    api: ESPNApiClient,
    fighter_id: str,
    event_item: Dict[str, Any],
) -> Optional[Fight]:
    """Process a single event item from the eventlog."""
    event_ref = event_item.get("event", {}).get("$ref", "")
    competition_ref = event_item.get("competition", {}).get("$ref", "")

    if "/leagues/ufc/" not in event_ref:
        return None

    try:
        competition_detail = api.get_competition_detail(competition_ref)
        competitors = competition_detail.get("competitors", [])

        opponent_id = None
        winner_id = None
        for comp in competitors:
            comp_id = str(comp.get("id", ""))
            is_winner = comp.get("winner", False)
            
            if comp_id == str(fighter_id):
                if is_winner:
                    winner_id = fighter_id
            else:
                opponent_id = comp_id
                if is_winner:
                    winner_id = comp_id

        if not opponent_id:
            return None

        event_date = competition_detail.get("date", "")
        
        method = ""
        status = competition_detail.get("status", {})
        if isinstance(status, dict):
            result = status.get("result", {})
            if isinstance(result, dict):
                method = result.get("displayName", "")
                if result.get("description"):
                    method += f" ({result['description']})"

        return Fight(
            fighter1_id=str(fighter_id),
            fighter2_id=str(opponent_id),
            winner_id=str(winner_id) if winner_id else "",
            event_name="",
            date=event_date,
            method=method,
        )

    except Exception:
        return None
