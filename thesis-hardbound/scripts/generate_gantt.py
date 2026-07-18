#!/usr/bin/env python3
"""Generate a table-style Gantt chart matching the school template layout."""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "gantt" / "project_schedule.csv"
OUT_PATH = ROOT / "gantt" / "project_gantt_chart.png"

PHASE_COLORS = {
    "Business Understanding": "#D94F4F",
    "Data Understanding": "#F1C232",
    "Data Preparation": "#6FA8DC",
    "Modeling": "#1F4E79",
    "Evaluation": "#52B788",
    "Deployment": "#8E5EA8",
}

HEADER_BG = "#1F3864"
HEADER_FG = "#FFFFFF"
GRID = "#BFBFBF"
TEXT = "#1A1A1A"

COL = {
    "phase": 1.35,
    "task": 0.55,
    "desc": 4.2,
    "in_charge": 2.4,
    "wks": 0.45,
    "week": 0.38,
}

ROW_H = 0.62
HEADER_H = 0.72


def load_tasks() -> list[dict[str, str | int]]:
    tasks: list[dict[str, str | int]] = []
    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            desc = re.sub(r"^T\d+\s*", "", row["Task"]).strip()
            tasks.append(
                {
                    "phase": row["Phase"],
                    "task_number": row["Task Number"],
                    "description": desc,
                    "in_charge": row["In-Charge"],
                    "duration": int(row["Duration (Weeks)"]),
                    "start": int(row["Start Week"]),
                    "end": int(row["End Week"]),
                }
            )
    return tasks


def col_x(col_name: str, week_index: int | None = None) -> float:
    x = 0.0
    for key in ("phase", "task", "desc", "in_charge", "wks"):
        if key == col_name:
            return x
        x += COL[key]
    if col_name == "week" and week_index is not None:
        return x + (week_index - 1) * COL["week"]
    return x


def total_width(num_weeks: int) -> float:
    return col_x("week", 1) + num_weeks * COL["week"]


def draw_cell(
    ax,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    facecolor: str = "white",
    edgecolor: str = GRID,
    linewidth: float = 0.8,
    zorder: int = 1,
) -> None:
    ax.add_patch(
        mpatches.Rectangle(
            (x, y),
            w,
            h,
            facecolor=facecolor,
            edgecolor=edgecolor,
            linewidth=linewidth,
            zorder=zorder,
        )
    )


def wrap_text(text: str, max_chars: int = 34) -> str:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join(current + [word])
        if len(candidate) <= max_chars:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return "\n".join(lines)


def main() -> None:
    tasks = load_tasks()
    num_weeks = max(int(t["end"]) for t in tasks)
    width = total_width(num_weeks)
    num_rows = len(tasks)
    height = HEADER_H * 2 + num_rows * ROW_H + 1.0

    fig_w = 24
    fig_h = max(14, num_rows * 0.42 + 3.2)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.set_xlim(0, width)
    ax.set_ylim(0, height)
    ax.axis("off")

    y_top = height - HEADER_H

    # Main header row
    headers = [
        ("phase", "PHASES", COL["phase"]),
        ("task", "TASK", COL["task"]),
        ("desc", "TASK DESCRIPTION", COL["desc"]),
        ("in_charge", "IN-CHARGE", COL["in_charge"]),
        ("wks", "WKS", COL["wks"]),
    ]
    for key, label, w in headers:
        x = col_x(key)
        draw_cell(ax, x, y_top, w, HEADER_H, facecolor=HEADER_BG, edgecolor=HEADER_BG)
        ax.text(
            x + w / 2,
            y_top + HEADER_H / 2,
            label,
            ha="center",
            va="center",
            color=HEADER_FG,
            fontsize=8.5,
            fontweight="bold",
            zorder=3,
        )

    timeline_x = col_x("week", 1)
    timeline_w = num_weeks * COL["week"]
    draw_cell(ax, timeline_x, y_top, timeline_w, HEADER_H, facecolor=HEADER_BG, edgecolor=HEADER_BG)
    ax.text(
        timeline_x + timeline_w / 2,
        y_top + HEADER_H / 2,
        "PROJECT TIMELINE (WEEKS)",
        ha="center",
        va="center",
        color=HEADER_FG,
        fontsize=8.5,
        fontweight="bold",
        zorder=3,
    )

    # Week number row
    y_week = y_top - HEADER_H
    for key, _, w in headers:
        x = col_x(key)
        draw_cell(ax, x, y_week, w, HEADER_H, facecolor=HEADER_BG, edgecolor=GRID)
    for week in range(1, num_weeks + 1):
        x = col_x("week", week)
        draw_cell(ax, x, y_week, COL["week"], HEADER_H, facecolor=HEADER_BG, edgecolor=GRID)
        ax.text(
            x + COL["week"] / 2,
            y_week + HEADER_H / 2,
            str(week),
            ha="center",
            va="center",
            color=HEADER_FG,
            fontsize=7,
            fontweight="bold",
            zorder=3,
        )

    # Group tasks by phase for merged phase column
    phase_groups: dict[str, list[dict[str, str | int]]] = defaultdict(list)
    for task in tasks:
        phase_groups[str(task["phase"])].append(task)

    y = y_week
    for phase, phase_tasks in phase_groups.items():
        phase_color = PHASE_COLORS[phase]
        group_h = len(phase_tasks) * ROW_H
        y -= group_h

        # Merged phase label cell
        draw_cell(ax, 0, y, COL["phase"], group_h, facecolor=phase_color, edgecolor=GRID)
        ax.text(
            COL["phase"] / 2,
            y + group_h / 2,
            phase,
            ha="center",
            va="center",
            rotation=90,
            color="white",
            fontsize=7.5,
            fontweight="bold",
            zorder=3,
        )

        row_y = y + group_h
        for task in phase_tasks:
            row_y -= ROW_H
            # Task metadata cells
            meta = [
                ("task", str(task["task_number"]), 8, "center"),
                ("desc", wrap_text(str(task["description"]), 40), 7, "left"),
                ("in_charge", wrap_text(str(task["in_charge"]), 22), 7, "left"),
                ("wks", str(task["duration"]), 8, "center"),
            ]
            for key, text, size, align in meta:
                x = col_x(key)
                w = COL[key]
                draw_cell(ax, x, row_y, w, ROW_H, facecolor="white", edgecolor=GRID)
                ax.text(
                    x + (0.08 if align == "left" else w / 2),
                    row_y + ROW_H / 2,
                    text,
                    ha=align,
                    va="center",
                    color=TEXT,
                    fontsize=size,
                    zorder=3,
                )

            # Timeline grid + colored blocks
            start = int(task["start"])
            end = int(task["end"])
            for week in range(1, num_weeks + 1):
                x = col_x("week", week)
                active = start <= week <= end
                draw_cell(
                    ax,
                    x,
                    row_y,
                    COL["week"],
                    ROW_H,
                    facecolor=phase_color if active else "white",
                    edgecolor=GRID,
                    linewidth=0.7,
                )

    # Legend
    legend_y = 0.35
    legend_x = col_x("phase")
    ax.text(
        legend_x,
        legend_y + 0.35,
        "Legend:",
        fontsize=9,
        fontweight="bold",
        color=TEXT,
        va="center",
    )
    lx = legend_x + 0.9
    for phase, color in PHASE_COLORS.items():
        ax.add_patch(
            mpatches.Rectangle(
                (lx, legend_y),
                0.35,
                0.35,
                facecolor=color,
                edgecolor=GRID,
                linewidth=0.6,
            )
        )
        ax.text(lx + 0.45, legend_y + 0.17, phase, fontsize=8, va="center", color=TEXT)
        lx += 2.55

    fig.savefig(OUT_PATH, dpi=220, bbox_inches="tight", pad_inches=0.15)
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
