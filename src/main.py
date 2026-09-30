from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter
from typing import Dict, List

from .crawler import build_fighter_graph, find_fighters_by_name
from .espn_api import ESPNApiClient
from .models import Fighter
from .visualizer import build_interactive_graph


def main() -> None:
    parser = argparse.ArgumentParser(description="Build UFC fighter network graph.")
    
    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Default crawl command (original functionality)
    crawl_parser = subparsers.add_parser("crawl", help="Crawl UFC fighter data")
    _add_crawl_args(crawl_parser)
    
    # ELO data command
    elo_parser = subparsers.add_parser("elo-data", help="Generate ELO-ready fight data")
    _add_elo_args(elo_parser)
    
    # Calculate ELO command
    calc_parser = subparsers.add_parser("calculate-elo", help="Calculate ELO ratings")
    calc_parser.add_argument(
        "--data-dir",
        default=os.path.join(os.getcwd(), "data"),
        help="Directory for data files.",
    )
    
    # Build ELO history command
    history_parser = subparsers.add_parser("elo-history", help="Build ELO history timeline")
    history_parser.add_argument(
        "--data-dir",
        default=os.path.join(os.getcwd(), "data"),
        help="Directory for data files.",
    )
    
    # Query top fighters at date
    top_parser = subparsers.add_parser("top-at-date", help="Get top fighters at a specific date")
    top_parser.add_argument("date", help="Date in YYYY-MM-DD format")
    top_parser.add_argument(
        "--top", "-n",
        type=int,
        default=10,
        help="Number of top fighters to show (default: 10)",
    )
    top_parser.add_argument(
        "--data-dir",
        default=os.path.join(os.getcwd(), "data"),
        help="Directory for data files.",
    )
    
    # Query fighter history
    fighter_parser = subparsers.add_parser("fighter-history", help="Get a fighter's ELO history")
    fighter_parser.add_argument("name", help="Fighter name (partial match)")
    fighter_parser.add_argument(
        "--data-dir",
        default=os.path.join(os.getcwd(), "data"),
        help="Directory for data files.",
    )
    
    # Largest ELO gains
    gains_parser = subparsers.add_parser("largest-gains", help="Get largest ELO gains from single fights")
    gains_parser.add_argument(
        "--top", "-n",
        type=int,
        default=20,
        help="Number of results to show (default: 20)",
    )
    gains_parser.add_argument(
        "--data-dir",
        default=os.path.join(os.getcwd(), "data"),
        help="Directory for data files.",
    )
    
    # Largest ELO losses
    losses_parser = subparsers.add_parser("largest-losses", help="Get largest ELO losses (most punishing losses)")
    losses_parser.add_argument(
        "--top", "-n",
        type=int,
        default=20,
        help="Number of results to show (default: 20)",
    )
    losses_parser.add_argument(
        "--data-dir",
        default=os.path.join(os.getcwd(), "data"),
        help="Directory for data files.",
    )
    
    # All-time peaks
    peaks_parser = subparsers.add_parser("all-time-peaks", help="Get all-time peak ELOs achieved")
    peaks_parser.add_argument(
        "--top", "-n",
        type=int,
        default=50,
        help="Number of results to show (default: 50)",
    )
    peaks_parser.add_argument(
        "--data-dir",
        default=os.path.join(os.getcwd(), "data"),
        help="Directory for data files.",
    )
    
    # Fighter analysis
    analysis_parser = subparsers.add_parser("fighter-analysis", help="Get comprehensive analysis for a fighter")
    analysis_parser.add_argument("name", help="Fighter name (partial match)")
    analysis_parser.add_argument(
        "--data-dir",
        default=os.path.join(os.getcwd(), "data"),
        help="Directory for data files.",
    )

    # Visualize top 10 ELO over time (bar chart race)
    viz_parser = subparsers.add_parser("visualize-elo-race", help="Create ELO bar chart race animation")
    viz_parser.add_argument(
        "--output",
        default=os.path.join(os.getcwd(), "output", "elo_race.mp4"),
        help="Output file path (.mp4 or .gif).",
    )
    viz_parser.add_argument(
        "--fps",
        type=float,
        default=None,
        help="Frames per second (default: auto-calculated from events/duration, 1 frame per event)",
    )
    viz_parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Animation duration in seconds (default: 60)",
    )
    viz_parser.add_argument(
        "--data-dir",
        default=os.path.join(os.getcwd(), "data"),
        help="Directory for data files.",
    )
    viz_parser.add_argument(
        "--start-date",
        default=None,
        help="Start date for animation (YYYY-MM-DD). Default: earliest event.",
    )
    viz_parser.add_argument(
        "--end-date",
        default=None,
        help="End date for animation (YYYY-MM-DD). Default: latest event.",
    )
    
    # Also add crawl args to main parser for backwards compatibility
    _add_crawl_args(parser)
    
    args = parser.parse_args()
    
    if args.command == "elo-data":
        run_elo_data(args)
    elif args.command == "calculate-elo":
        run_calculate_elo(args)
    elif args.command == "elo-history":
        run_elo_history(args)
    elif args.command == "top-at-date":
        run_top_at_date(args)
    elif args.command == "fighter-history":
        run_fighter_history(args)
    elif args.command == "largest-gains":
        run_largest_gains(args)
    elif args.command == "largest-losses":
        run_largest_losses(args)
    elif args.command == "all-time-peaks":
        run_all_time_peaks(args)
    elif args.command == "fighter-analysis":
        run_fighter_analysis(args)
    elif args.command == "visualize-elo-race":
        run_visualize_elo_race(args)
    else:
        run_crawl(args)


def _add_crawl_args(parser):
    """Add crawler arguments to a parser."""
    parser.add_argument(
        "--data-dir",
        default=os.path.join(os.getcwd(), "data"),
        help="Directory for cached API data and outputs.",
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.join(os.getcwd(), "output"),
        help="Directory for visualization output.",
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=0.25,
        help="Seconds to wait between API requests (default: 0.25).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max number of fighters to process (0 = unlimited).",
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=0,
        help="Max BFS depth (0 = unlimited, only used with --names).",
    )
    parser.add_argument(
        "--names",
        type=str,
        default=None,
        help="Path to file with fighter names (one per line) to use as seeds.",
    )


def _add_elo_args(parser):
    """Add ELO data arguments to a parser."""
    parser.add_argument(
        "--data-dir",
        default=os.path.join(os.getcwd(), "data"),
        help="Directory for data files.",
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=0.15,
        help="Seconds to wait between API requests (default: 0.15).",
    )


def run_crawl(args) -> None:
    """Run the crawler to build fighter graph."""
    cache_dir = os.path.join(args.data_dir, "cache")
    os.makedirs(cache_dir, exist_ok=True)
    os.makedirs(args.output_dir, exist_ok=True)

    print("Initializing ESPN API client...")
    api = ESPNApiClient(cache_dir=cache_dir, rate_limit_seconds=args.rate_limit)
    
    print("Fetching list of all UFC athletes from ESPN...")
    all_athletes = api.get_all_athletes()
    print(f"Found {len(all_athletes)} athletes in UFC database")
    
    # Determine seed fighters
    if args.names:
        names = _load_names_from_file(args.names)
        print(f"\nLooking up {len(names)} fighter names...")
        seed_fighters = find_fighters_by_name(api, names, all_athletes)
        skip_bfs = False
    else:
        seed_fighters = all_athletes
        # Don't skip BFS - we want to discover fighters through fight history
        # The API pagination is broken, so BFS helps find the remaining ~800 fighters
        skip_bfs = False
        print(f"Note: Using BFS traversal to discover all fighters through fight history")
        
    if args.limit and args.limit < len(seed_fighters) and not args.names:
        seed_fighters = seed_fighters[:args.limit]
        print(f"Limiting initial seeds to {args.limit}")

    print(f"\nBuilding fighter graph (depth={args.depth}, max={args.limit})...")
    graph, fighters = build_fighter_graph(
        api, 
        seed_fighters, 
        skip_bfs=skip_bfs,
        max_depth=args.depth,
        max_fighters=args.limit,
    )

    fighters_csv_path = os.path.join(args.data_dir, "fighters.csv")
    graph_json_path = os.path.join(args.data_dir, "fight_graph.json")
    html_path = os.path.join(args.output_dir, "ufc_fighter_network.html")

    print("\nGenerating outputs...")
    fight_counts = _count_fights(graph)
    _write_fighters_csv(fighters_csv_path, fighters, fight_counts)
    _write_graph_json(graph_json_path, graph, fighters)
    build_interactive_graph(graph, fighters, html_path)

    print(f"\n{'='*50}")
    print(f"SUMMARY")
    print(f"{'='*50}")
    print(f"Fighters processed: {len(fighters)}")
    print(f"UFC Fights found: {graph.number_of_edges()}")
    print(f"Graph nodes: {graph.number_of_nodes()}")
    print(f"\nOutputs:")
    print(f"  - {fighters_csv_path}")
    print(f"  - {graph_json_path}")
    print(f"  - {html_path}")


def run_elo_history(args) -> None:
    """Build ELO history timeline data."""
    from .elo_history import build_elo_history
    
    data_dir = args.data_dir
    elo_ratings_path = os.path.join(data_dir, "elo_ratings.json")
    
    if not os.path.exists(elo_ratings_path):
        print(f"ERROR: {elo_ratings_path} not found. Run 'calculate-elo' first.")
        return
    
    print("=" * 60)
    print("BUILDING ELO HISTORY TIMELINE")
    print("=" * 60)
    
    result = build_elo_history(elo_ratings_path, data_dir)
    
    print(f"\n{'='*60}")
    print("ELO HISTORY BUILD COMPLETE")
    print(f"{'='*60}")
    print(f"\nOutputs:")
    print(f"  - {data_dir}/elo_timeline.json    (top 10 at each event)")
    print(f"  - {data_dir}/elo_by_fighter.json  (individual fighter histories)")
    print(f"  - {data_dir}/elo_matrix.csv       (wide format: dates x fighters)")
    print(f"  - {data_dir}/current_rankings.csv (current rankings)")
    print(f"\nQuery commands:")
    print(f"  python -m src.main top-at-date 2023-01-01")
    print(f"  python -m src.main fighter-history 'Alex Pereira'")


def run_top_at_date(args) -> None:
    """Get top fighters at a specific date."""
    from .elo_history import get_top_fighters_at_date_full
    
    data_dir = args.data_dir
    history_path = os.path.join(data_dir, "elo_by_fighter.json")
    
    if not os.path.exists(history_path):
        print(f"ERROR: {history_path} not found. Run 'elo-history' first.")
        return
    
    target_date = args.date
    top_n = args.top
    top_fighters = get_top_fighters_at_date_full(history_path, target_date, top_n)
    
    if not top_fighters:
        print(f"No data found for date: {target_date}")
        return
    
    print(f"\n{'='*50}")
    print(f"TOP {top_n} FIGHTERS AS OF {target_date}")
    print(f"{'='*50}")
    print(f"{'Rank':<6}{'Name':<30}{'ELO':<10}")
    print("-" * 50)
    
    for fighter in top_fighters:
        print(f"{fighter['rank']:<6}{fighter['name']:<30}{fighter['elo']:<10.1f}")


def run_fighter_history(args) -> None:
    """Get a fighter's ELO history."""
    from .elo_history import get_fighter_history
    
    data_dir = args.data_dir
    history_path = os.path.join(data_dir, "elo_by_fighter.json")
    
    if not os.path.exists(history_path):
        print(f"ERROR: {history_path} not found. Run 'elo-history' first.")
        return
    
    fighter_name = args.name
    fighter_data = get_fighter_history(history_path, fighter_name)
    
    if not fighter_data:
        print(f"Fighter not found: {fighter_name}")
        return
    
    print(f"\n{'='*120}")
    print(f"ELO HISTORY: {fighter_data['name']}")
    print(f"{'='*120}")
    print(f"Current ELO: {fighter_data['current_elo']:.1f}")
    print(f"Peak ELO: {fighter_data['peak_elo']:.1f}")
    print(f"Total UFC Fights: {fighter_data['fights']}")
    print(f"\n{'Date':<12}{'Event':<28}{'Opponent':<22}{'Opp ELO':<10}{'Result':<6}{'ELO Δ':<10}{'ELO':<10}")
    print("-" * 120)
    
    for entry in fighter_data["history"]:
        date = entry["date"][:10]
        event = entry["event"][:26] + "..." if len(entry["event"]) > 28 else entry["event"]
        opponent = entry["opponent_name"][:20] + "..." if len(entry["opponent_name"]) > 22 else entry["opponent_name"]
        opp_elo = entry.get("opponent_elo_before", 1500.0)
        result = entry["result"]
        elo_change = entry["elo_change"]
        elo_after = entry["elo_after"]
        change_str = f"+{elo_change:.1f}" if elo_change >= 0 else f"{elo_change:.1f}"
        print(f"{date:<12}{event:<28}{opponent:<22}{opp_elo:<10.1f}{result:<6}{change_str:<10}{elo_after:<10.1f}")


def run_largest_gains(args) -> None:
    """Get largest ELO gains from single fights."""
    from .elo_history import get_largest_elo_gains
    
    data_dir = args.data_dir
    history_path = os.path.join(data_dir, "elo_by_fighter.json")
    
    if not os.path.exists(history_path):
        print(f"ERROR: {history_path} not found. Run 'elo-history' first.")
        return
    
    top_n = args.top
    gains = get_largest_elo_gains(history_path, top_n)
    
    if not gains:
        print("No ELO gains found.")
        return
    
    print(f"\n{'='*100}")
    print(f"LARGEST ELO GAINS (Top {top_n})")
    print(f"{'='*100}")
    print(f"{'Rank':<6}{'Fighter':<25}{'Date':<12}{'Opponent':<25}{'ELO Δ':<10}{'Method':<15}{'Title':<6}")
    print("-" * 100)
    
    for i, gain in enumerate(gains):
        title_str = "Yes" if gain["is_title_fight"] else "No"
        method = gain["method"][:13] + "..." if len(gain["method"]) > 15 else gain["method"]
        print(
            f"{i+1:<6}"
            f"{gain['fighter_name']:<25}"
            f"{gain['date'][:10]:<12}"
            f"{gain['opponent_name']:<25}"
            f"+{gain['elo_change']:.1f}"
            f"{method:<15}"
            f"{title_str:<6}"
        )


def run_largest_losses(args) -> None:
    """Get largest ELO losses (most punishing losses)."""
    from .elo_history import get_largest_elo_losses
    
    data_dir = args.data_dir
    history_path = os.path.join(data_dir, "elo_by_fighter.json")
    
    if not os.path.exists(history_path):
        print(f"ERROR: {history_path} not found. Run 'elo-history' first.")
        return
    
    top_n = args.top
    losses = get_largest_elo_losses(history_path, top_n)
    
    if not losses:
        print("No ELO losses found.")
        return
    
    print(f"\n{'='*100}")
    print(f"LARGEST ELO LOSSES (Most Punishing - Top {top_n})")
    print(f"{'='*100}")
    print(f"{'Rank':<6}{'Fighter':<25}{'Date':<12}{'Opponent':<25}{'ELO Δ':<10}{'Method':<15}{'Title':<6}")
    print("-" * 100)
    
    for i, loss in enumerate(losses):
        title_str = "Yes" if loss["is_title_fight"] else "No"
        method = loss["method"][:13] + "..." if len(loss["method"]) > 15 else loss["method"]
        print(
            f"{i+1:<6}"
            f"{loss['fighter_name']:<25}"
            f"{loss['date'][:10]:<12}"
            f"{loss['opponent_name']:<25}"
            f"{loss['elo_change']:.1f}"
            f"{method:<15}"
            f"{title_str:<6}"
        )


def run_all_time_peaks(args) -> None:
    """Get all-time peak ELOs achieved."""
    from .elo_history import get_all_time_peaks
    
    data_dir = args.data_dir
    history_path = os.path.join(data_dir, "elo_by_fighter.json")
    
    if not os.path.exists(history_path):
        print(f"ERROR: {history_path} not found. Run 'elo-history' first.")
        return
    
    top_n = args.top
    peaks = get_all_time_peaks(history_path, top_n)
    
    if not peaks:
        print("No peak ELO data found.")
        return
    
    print(f"\n{'='*80}")
    print(f"ALL-TIME PEAK ELOs (Top {top_n})")
    print(f"{'='*80}")
    print(f"{'Rank':<6}{'Fighter':<30}{'Peak ELO':<12}{'Current ELO':<14}{'Fights':<8}")
    print("-" * 80)
    
    for i, peak in enumerate(peaks):
        current = peak["current_elo"]
        diff = peak["peak_elo"] - current
        diff_str = f"(-{diff:.1f})" if diff > 0 else "(at peak)"
        print(
            f"{i+1:<6}"
            f"{peak['fighter_name']:<30}"
            f"{peak['peak_elo']:.1f}"
            f"{current:.1f} {diff_str:<10}"
            f"{peak['fights']:<8}"
        )


def run_fighter_analysis(args) -> None:
    """Get comprehensive analysis for a fighter."""
    from .elo_history import get_fighter_analysis
    
    data_dir = args.data_dir
    history_path = os.path.join(data_dir, "elo_by_fighter.json")
    
    if not os.path.exists(history_path):
        print(f"ERROR: {history_path} not found. Run 'elo-history' first.")
        return
    
    fighter_name = args.name
    analysis = get_fighter_analysis(history_path, fighter_name)
    
    if not analysis:
        print(f"Fighter not found: {fighter_name}")
        return
    
    print(f"\n{'='*80}")
    print(f"FIGHTER ANALYSIS: {analysis['name']}")
    print(f"{'='*80}")
    print(f"Current ELO: {analysis['current_elo']:.1f}")
    print(f"Peak ELO: {analysis['peak_elo']:.1f}")
    print(f"Record: {analysis['record']}")
    print(f"Total Fights: {analysis['total_fights']}")
    print(f"Title Fights: {analysis['title_fights']}")
    print(f"Finishes: {analysis['finishes']}")
    
    if analysis.get("best_gain"):
        bg = analysis["best_gain"]
        print(f"\n{'='*80}")
        print("BEST ELO GAIN:")
        print(f"  Date: {bg['date'][:10]}")
        print(f"  Event: {bg['event']}")
        print(f"  Opponent: {bg['opponent_name']} (ELO: {bg['opponent_elo_before']:.1f})")
        print(f"  ELO Change: +{bg['elo_change']:.1f} ({bg['elo_before']:.1f} → {bg['elo_after']:.1f})")
        print(f"  Method: {bg['method']}")
        print(f"  Title Fight: {'Yes' if bg['is_title_fight'] else 'No'}")
    
    if analysis.get("worst_loss"):
        wl = analysis["worst_loss"]
        print(f"\n{'='*80}")
        print("WORST ELO LOSS:")
        print(f"  Date: {wl['date'][:10]}")
        print(f"  Event: {wl['event']}")
        print(f"  Opponent: {wl['opponent_name']} (ELO: {wl['opponent_elo_before']:.1f})")
        print(f"  ELO Change: {wl['elo_change']:.1f} ({wl['elo_before']:.1f} → {wl['elo_after']:.1f})")
        print(f"  Method: {wl['method']}")
        print(f"  Title Fight: {'Yes' if wl['is_title_fight'] else 'No'}")


def run_visualize_elo_race(args) -> None:
    """Create ELO bar chart race animation."""
    from .visualizer_elo import build_elo_race_animation

    data_dir = args.data_dir
    timeline_path = os.path.join(data_dir, "elo_timeline.json")
    output_path = args.output
    fps = args.fps
    duration = args.duration
    start_date = args.start_date
    end_date = args.end_date

    if not os.path.exists(timeline_path):
        print(f"ERROR: {timeline_path} not found. Run 'elo-history' first.")
        return

    print("\n============================================================")
    print("BUILDING ELO BAR CHART RACE")
    print("============================================================")
    print(f"Timeline: {timeline_path}")
    print(f"Output: {output_path}")
    if fps is not None:
        print(f"FPS: {fps} | Duration: {duration}s")
    else:
        print(f"Duration: {duration}s (fps will be auto-calculated)")
    if start_date or end_date:
        print(f"Date range: {start_date or 'start'} to {end_date or 'end'}")

    try:
        result_path = build_elo_race_animation(
            timeline_path=timeline_path,
            output_path=output_path,
            fps=fps,  # None means auto-calculate
            duration=duration,
            start_date=start_date,
            end_date=end_date,
        )
        print(f"\nSaved animation to {result_path}")
    except Exception as exc:
        print(f"\nERROR creating animation: {exc}")
        print("If saving MP4 fails, try outputting a .gif instead.")


def run_calculate_elo(args) -> None:
    """Calculate ELO ratings from elo_ready.json."""
    from .elo_calculator import (
        run_elo_calculation,
        print_top_fighters,
        get_elo_distribution,
    )
    
    data_dir = args.data_dir
    elo_ready_path = os.path.join(data_dir, "elo_ready.json")
    output_path = os.path.join(data_dir, "elo_ratings.json")
    
    if not os.path.exists(elo_ready_path):
        print(f"ERROR: {elo_ready_path} not found. Run 'elo-data' first.")
        return
    
    print("=" * 60)
    print("CALCULATING MMA ELO RATINGS")
    print("=" * 60)
    
    # Run ELO calculation
    fights, fighters = run_elo_calculation(elo_ready_path, output_path)
    
    # Print top fighters
    print_top_fighters(fighters, n=25)
    
    # Print distribution stats
    dist = get_elo_distribution(fighters)
    print(f"\n{'='*60}")
    print("ELO DISTRIBUTION")
    print(f"{'='*60}")
    print(f"Total fighters: {dist['count']}")
    print(f"Mean ELO: {dist['mean']}")
    print(f"Median ELO: {dist['median']}")
    print(f"Std Dev: {dist['std_dev']}")
    print(f"Range: {dist['min']} - {dist['max']}")
    print(f"\nDistribution:")
    print(f"  1200-1399 (Journeymen): {dist['range_1200_1400']}")
    print(f"  1400-1599 (Average):    {dist['range_1400_1600']}")
    print(f"  1600-1799 (Strong):     {dist['range_1600_1800']}")
    print(f"  1800+     (Elite):      {dist['range_1800_plus']}")
    
    print(f"\nOutput saved to: {output_path}")


def run_elo_data(args) -> None:
    """Generate ELO-ready fight data from existing crawled data."""
    from .gender_filter import (
        load_fighter_genders,
        filter_male_fighters,
        get_gender_stats,
    )
    from .fight_enhancer import enhance_fights_from_graph
    from .elo_builder import build_elo_ready_data
    
    data_dir = args.data_dir
    cache_dir = os.path.join(data_dir, "cache")
    
    # Check required files exist
    fighters_csv = os.path.join(data_dir, "fighters.csv")
    fight_graph = os.path.join(data_dir, "fight_graph.json")
    
    if not os.path.exists(fighters_csv) or not os.path.exists(fight_graph):
        print("ERROR: Required files not found. Run crawl first:")
        print("  python -m src.main crawl --names data/seed_fighters.txt --depth 3 --limit 800")
        return
    
    print("=" * 60)
    print("GENERATING ELO-READY FIGHT DATA (MEN'S ONLY)")
    print("=" * 60)
    
    # Initialize API client
    api = ESPNApiClient(cache_dir=cache_dir, rate_limit_seconds=args.rate_limit)
    
    # Load fighter names
    fighter_names = {}
    fighter_ids = []
    with open(fighters_csv, "r") as f:
        for line in f:
            if line.startswith("id"):
                continue
            parts = line.strip().split(",")
            if len(parts) >= 2:
                fighter_names[parts[0]] = parts[1]
                fighter_ids.append(parts[0])
    
    # Also get fighter IDs from fight graph (includes opponents)
    with open(fight_graph, "r") as f:
        graph_data = json.load(f)
    for edge in graph_data["edges"]:
        if edge["source"] not in fighter_ids:
            fighter_ids.append(edge["source"])
        if edge["target"] not in fighter_ids:
            fighter_ids.append(edge["target"])
    
    print(f"\nStep 1: Loading fighter genders...")
    gender_cache = load_fighter_genders(
        api, 
        fighter_ids, 
        cache_file=os.path.join(data_dir, "fighter_genders.json")
    )
    
    gender_stats = get_gender_stats(gender_cache)
    print(f"  Male: {gender_stats['MALE']}, Female: {gender_stats['FEMALE']}, Unknown: {gender_stats['UNKNOWN']}")
    
    # Filter to male fighters
    male_fighter_ids = filter_male_fighters(fighter_ids, gender_cache)
    print(f"  Using {len(male_fighter_ids)} male fighters")
    
    # Update fighter names for any we're missing
    for fid in male_fighter_ids:
        if fid not in fighter_names:
            try:
                detail = api.get_athlete_detail(fid)
                fighter_names[fid] = detail.get("displayName", "Unknown")
            except:
                fighter_names[fid] = "Unknown"
    
    print(f"\nStep 2: Enhancing fight data with event names, methods, title fights...")
    enhanced_fights_path = os.path.join(data_dir, "enhanced_fights.json")
    enhance_fights_from_graph(
        api,
        fight_graph,
        fighters_csv,
        enhanced_fights_path,
    )
    
    print(f"\nStep 3: Building chronological ELO-ready data...")
    elo_ready_path = os.path.join(data_dir, "elo_ready.json")
    fight_records = build_elo_ready_data(
        enhanced_fights_path,
        male_fighter_ids,
        fighter_names,
        elo_ready_path,
    )
    
    print(f"\n{'='*60}")
    print("ELO DATA GENERATION COMPLETE")
    print(f"{'='*60}")
    print(f"Output: {elo_ready_path}")
    print(f"\nNext steps:")
    print("  1. Load elo_ready.json")
    print("  2. Implement your ELO algorithm")
    print("  3. Process fights chronologically, updating ELO after each")
    print("  4. Use multipliers for: finish bonus, title fight, opponent strength")


def _load_names_from_file(filepath: str) -> List[str]:
    """Load fighter names from a text file (one per line)."""
    names = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            name = line.strip()
            if name and not name.startswith("#"):
                names.append(name)
    return names


def _count_fights(graph) -> Counter:
    """Count UFC fights per fighter. Each edge = 1 fight for both participants."""
    counter: Counter = Counter()
    for node in graph.nodes():
        counter[node] = graph.degree(node)
    return counter


def _write_fighters_csv(path: str, fighters: Dict[str, Fighter], fight_counts: Counter) -> None:
    rows: List[Dict[str, str]] = []
    for fighter_id, fighter in fighters.items():
        rows.append(
            {
                "id": fighter_id,
                "name": fighter.name,
                "record": fighter.record,
                "total_ufc_fights": str(fight_counts.get(fighter_id, 0)),
            }
        )

    rows.sort(key=lambda row: row["name"])
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id", "name", "record", "total_ufc_fights"])
        writer.writeheader()
        writer.writerows(rows)


def _write_graph_json(path: str, graph, fighters: Dict[str, Fighter]) -> None:
    nodes = [
        {"id": fighter.id, "name": fighter.name, "record": fighter.record}
        for fighter in fighters.values()
    ]
    edges = []
    for source, target, attrs in graph.edges(data=True):
        edges.append(
            {
                "source": source,
                "target": target,
                "winner_id": attrs.get("winner_id") or "",
                "event_name": attrs.get("event_name") or "",
                "date": attrs.get("date") or "",
                "method": attrs.get("method") or "",
            }
        )
    payload = {"nodes": nodes, "edges": edges}
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, indent=2, fp=handle)


if __name__ == "__main__":
    main()
