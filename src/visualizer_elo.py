from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter, FFMpegWriter


UFC_RED = "#D00000"
UFC_GOLD = "#FFD700"
UFC_DARK = "#1a1a1a"
UFC_TEXT = "#f2f2f2"


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _rank_colors(n: int) -> List[str]:
    """Create a red->gold gradient list for ranks 1..n."""
    start = _hex_to_rgb(UFC_RED)
    end = _hex_to_rgb(UFC_GOLD)
    colors = []
    for i in range(n):
        t = i / max(1, n - 1)
        rgb = tuple(int(start[j] + (end[j] - start[j]) * t) for j in range(3))
        colors.append(_rgb_to_hex(rgb))
    return colors


def _calculate_fps_from_events(
    num_events: int,
    duration: int,
) -> float:
    """
    Calculate fps needed to show all events in the given duration.
    One frame per event.
    """
    if num_events == 0 or duration == 0:
        return 30.0  # Default
    
    fps = num_events / duration
    return fps


def _filter_timeline_by_date(
    timeline: List[Dict[str, Any]],
    start_date: Optional[str],
    end_date: Optional[str],
) -> List[Dict[str, Any]]:
    """Filter timeline events to only include those within the date range."""
    filtered = []
    for event in timeline:
        event_date = event.get("date", "")[:10]  # Extract YYYY-MM-DD
        if start_date and event_date < start_date:
            continue
        if end_date and event_date > end_date:
            continue
        filtered.append(event)
    return filtered


def build_elo_race_animation(
    timeline_path: str,
    output_path: str,
    fps: Optional[float] = None,
    duration: int = 60,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> str:
    """
    Build a bar chart race for top 10 ELO over time.

    Args:
        timeline_path: Path to elo_timeline.json
        output_path: Path to output .mp4 or .gif
        fps: Optional frames per second. If None, calculated from events/duration (1 frame per event)
        duration: Total duration in seconds
        start_date: Optional start date (YYYY-MM-DD) to filter events
        end_date: Optional end date (YYYY-MM-DD) to filter events
    """
    if not os.path.exists(timeline_path):
        raise FileNotFoundError(f"Timeline file not found: {timeline_path}")

    with open(timeline_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    timeline = data.get("timeline", [])
    if not timeline:
        raise ValueError("Timeline is empty. Run 'elo-history' first.")

    # Filter by date range if specified, default to exclude future events
    # Default end_date is 2026-01-01 to exclude future events
    default_end_date = "2026-01-01"
    if end_date is None:
        end_date = default_end_date
    
    timeline = _filter_timeline_by_date(timeline, start_date, end_date)
    if not timeline:
        raise ValueError(f"No events found between {start_date or 'start'} and {end_date or 'end'}")

    # Calculate fps from events and duration (1 frame per event)
    if fps is None:
        fps = _calculate_fps_from_events(len(timeline), duration)
        print(f"Timeline: {len(timeline)} events")
        print(f"Duration: {duration} seconds")
        print(f"Calculated fps: {fps:.3f} (1 frame per event)")
    else:
        print(f"Timeline: {len(timeline)} events")
        print(f"Using specified fps: {fps}")
        print(f"Duration: {duration} seconds")
    
    # Use all events as frames (1 frame per event)
    frames = timeline

    # Smaller figure size for better fit
    fig, ax = plt.subplots(figsize=(12, 7), dpi=140)
    fig.patch.set_facecolor(UFC_DARK)
    ax.set_facecolor(UFC_DARK)

    colors = _rank_colors(10)

    def _truncate_name(name: str, max_len: int = 22) -> str:
        """Truncate long fighter names to fit on screen."""
        if len(name) <= max_len:
            return name
        return name[:max_len - 3] + "..."

    frame_count = [0]  # Track frame rendering in closure
    def animate(frame_index: int) -> None:
        # Ensure we don't go out of bounds
        if frame_index >= len(frames):
            print(f"Warning: frame_index {frame_index} >= {len(frames)}, clamping")
            frame_index = len(frames) - 1
        
        frame_count[0] += 1
        if frame_count[0] % 500 == 0:
            print(f"Rendering frame {frame_count[0]} / {len(frames)}...")
        
        ax.clear()
        ax.set_facecolor(UFC_DARK)

        frame = frames[frame_index]
        top_10 = frame.get("top_10", [])

        # Sort by ELO desc to ensure correct ordering
        sorted_fighters = sorted(top_10, key=lambda x: x["elo"], reverse=True)

        names = [f["name"] for f in sorted_fighters]
        elos = [f["elo"] for f in sorted_fighters]

        # Truncate long names to fit (shorter for smaller figure)
        names_truncated = [_truncate_name(name, max_len=22) for name in names]

        # Reverse for barh so #1 is at top
        names_rev = list(reversed(names_truncated))
        elos_rev = list(reversed(elos))
        colors_rev = list(reversed(colors[: len(elos_rev)]))

        ax.barh(names_rev, elos_rev, color=colors_rev, edgecolor="none")

        # Dynamic x-axis scaling based on actual data range
        if elos:
            min_elo = min(elos)
            max_elo = max(elos)
            # Add padding: 20 below min, 30 above max
            # But ensure we don't go below 1400 (most top fighters are 1600+)
            x_min = max(1400, min_elo - 20)
            x_max = max_elo + 30
            ax.set_xlim(x_min, x_max)
        else:
            ax.set_xlim(1600, 2000)

        # Title and subtitles (smaller fonts)
        date_str = frame.get("date", "")[:10]
        event_name = frame.get("event", "")
        # Truncate long event names
        event_truncated = _truncate_name(event_name, max_len=45)
        ax.set_title(
            f"UFC ELO Top 10  •  {date_str}\n{event_truncated}",
            color=UFC_TEXT,
            fontsize=12,
            fontweight="bold",
            pad=10,
        )

        # Style axes - smaller fonts for better fit
        ax.tick_params(axis="x", colors=UFC_TEXT, labelsize=9)
        ax.tick_params(axis="y", colors=UFC_TEXT, labelsize=9)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.grid(axis="x", color="#333333", linestyle="--", alpha=0.4)

        # Label ELO values (smaller font)
        for i, elo in enumerate(elos_rev):
            ax.text(
                elo + 3,
                i,
                f"{elo:.1f}",
                va="center",
                ha="left",
                color=UFC_TEXT,
                fontsize=8,
            )

    # Use calculated fps for interval and writer
    interval_ms = 1000 / fps if fps > 0 else 33.33  # Standard interval based on fps
    
    anim = FuncAnimation(
        fig,
        animate,
        frames=len(frames),
        interval=interval_ms,
        repeat=False,
    )

    output_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Use calculated fps to match duration
    if output_path.endswith(".gif"):
        writer = PillowWriter(fps=fps)
    else:
        writer = FFMpegWriter(fps=fps)
    
    print(f"Saving animation: {len(frames)} frames at {fps:.3f} fps = {len(frames)/fps:.2f} seconds")
    
    anim.save(output_path, writer=writer)
    plt.close(fig)
    
    print(f"Animation saved to {output_path}")
    return output_path

