from __future__ import annotations

import os
from typing import Dict

import networkx as nx
from pyvis.network import Network

from .models import Fighter


def build_interactive_graph(
    graph: nx.MultiDiGraph,
    fighters: Dict[str, Fighter],
    output_path: str,
    height: str = "800px",
    width: str = "100%",
) -> None:
    """Build an interactive HTML visualization of the fighter network."""
    
    # Create network with notebook=False to avoid template issues
    net = Network(
        height=height, 
        width=width, 
        directed=False,  # Undirected graph
        bgcolor="#111111", 
        font_color="#eeeeee",
        notebook=False,
        cdn_resources="remote",
    )
    net.barnes_hut()

    # Add nodes
    for node_id in graph.nodes:
        fighter = fighters.get(node_id)
        label = fighter.name if fighter and fighter.name else str(node_id)
        # Truncate long names
        if len(label) > 20:
            label = label[:17] + "..."
        
        fights = graph.degree(node_id)
        size = 10 + min(40, fights * 1.5)
        
        title_parts = [f"<b>{fighter.name if fighter else node_id}</b>"]
        title_parts.append(f"ID: {node_id}")
        title_parts.append(f"Fights: {fights}")
        if fighter and fighter.record:
            title_parts.append(f"Record: {fighter.record}")
        title = "<br>".join(title_parts)
        
        net.add_node(str(node_id), label=label, size=size, title=title)

    # Add edges
    for source, target, attrs in graph.edges(data=True):
        event_name = attrs.get("event_name") or ""
        date = attrs.get("date") or ""
        method = attrs.get("method") or ""
        winner = attrs.get("winner_id") or ""
        
        title_parts = []
        if date:
            title_parts.append(f"Date: {date[:10]}")
        if event_name:
            title_parts.append(f"Event: {event_name}")
        if method:
            title_parts.append(f"Method: {method}")
        if winner:
            title_parts.append(f"Winner: {winner}")
        
        title = "<br>".join(title_parts) if title_parts else None
        net.add_edge(str(source), str(target), title=title)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Save HTML - use save_graph instead of show to avoid template issues
    try:
        net.save_graph(output_path)
        print(f"Visualization saved to: {output_path}")
    except Exception as e:
        print(f"Warning: Could not save visualization: {e}")
        # Fallback: write minimal HTML
        _write_fallback_html(output_path, graph, fighters)


def _write_fallback_html(output_path: str, graph: nx.MultiDiGraph, fighters: Dict[str, Fighter]) -> None:
    """Write a simple fallback HTML if pyvis fails."""
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>UFC Fighter Network</title>
    <style>
        body {{ font-family: Arial, sans-serif; background: #111; color: #eee; padding: 20px; }}
        h1 {{ color: #fff; }}
        .stats {{ margin: 20px 0; }}
        table {{ border-collapse: collapse; width: 100%; max-width: 800px; }}
        th, td {{ border: 1px solid #333; padding: 8px; text-align: left; }}
        th {{ background: #222; }}
    </style>
</head>
<body>
    <h1>UFC Fighter Network</h1>
    <div class="stats">
        <p>Total Fighters: {len(fighters)}</p>
        <p>Total Fights: {graph.number_of_edges()}</p>
    </div>
    <p>Interactive visualization failed to generate. Check data/fight_graph.json for graph data.</p>
</body>
</html>"""
    with open(output_path, "w") as f:
        f.write(html)
    print(f"Fallback HTML saved to: {output_path}")
