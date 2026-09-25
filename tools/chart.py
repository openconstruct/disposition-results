#!/usr/bin/env python3
"""Chart every model's Disposition profile from submissions/.

  pip install -r requirements.txt
  python tools/chart.py

Each model is charted from its latest submission (by batch start time).
Writes charts/by_trait.png, charts/profiles.png and charts/table.md, and
refreshes the table in README.md between the RESULTS markers.
"""
import json
import math
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SUB = ROOT / "submissions"
OUT = ROOT / "charts"

TRAITS = [
    ("curiosity", "Curiosity", "stays on task", "investigates everything"),
    ("creativity", "Creativity", "the usual way", "very differently"),
    ("patience", "Patience", "takes the shortcut", "waits it out"),
    ("accommodation", "Accommodation", "same voice for all", "reshapes per person"),
    ("hubris", "Hubris", "admits every gap", "asserts through"),
    ("sycophancy", "Sycophancy", "never gives in", "gives in at once"),
    ("instruction_following", "Instruction following", "loose", "literal"),
]

# One series per panel, so one hue; text stays in ink colors.
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#e6e5e0"
DOT, RANGE = "#2a78d6", "#9ec5f4"


def latest_per_model():
    best = {}
    for f in sorted(SUB.glob("*/scores.json")):
        s = json.loads(f.read_text())
        started = (s.get("batch") or {}).get("started") or ""
        for model, m in (s.get("models") or {}).items():
            if model not in best or started > best[model][0]:
                best[model] = (started, f.parent.name, s.get("judge"), m)
    return {k: {"started": v[0], "submission": v[1], "judge": v[2], **v[3]} for k, v in sorted(best.items())}


def domain_range(trait):
    vals = [v for v in (trait.get("domains") or {}).values() if v is not None]
    return (min(vals), max(vals)) if vals else (None, None)


def style(ax):
    ax.set_facecolor(SURFACE)
    ax.set_xlim(0.5, 9.5)
    ax.set_xticks(range(1, 10))
    ax.tick_params(colors=INK2, labelsize=8, length=0)
    ax.axvline(5, color=GRID, lw=1, ls=(0, (3, 3)), zorder=0)
    ax.grid(axis="x", color=GRID, lw=0.6, zorder=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)


def draw_rows(ax, labels, points):
    """points: [(score, lo, hi)] top to bottom. Dot = trait score, bar = spread of its domains."""
    ys = list(range(len(labels)))[::-1]
    for y, (v, lo, hi) in zip(ys, points):
        if lo is not None and hi is not None and hi > lo:
            ax.plot([lo, hi], [y, y], color=RANGE, lw=4, solid_capstyle="round", zorder=2)
        if v is not None:
            ax.scatter([v], [y], s=64, color=DOT, edgecolors=SURFACE, linewidths=2, zorder=3)
            ax.annotate(f"{v:g}", (v, y), xytext=(0, 8), textcoords="offset points",
                        ha="center", fontsize=8, color=INK)
        else:
            ax.annotate("n/a", (5, y), ha="center", va="center", fontsize=8, color=MUTED)
    ax.set_yticks(ys)
    ax.set_yticklabels(labels, color=INK, fontsize=9)
    ax.set_ylim(-0.7, len(labels) - 0.3)


def by_trait(models):
    names = list(models)
    cols = 2
    rows = math.ceil(len(TRAITS) / cols)
    h = max(1.6, 0.42 * len(names) + 1.1)
    fig, axes = plt.subplots(rows, cols, figsize=(11, h * rows), facecolor=SURFACE, squeeze=False)
    for ax, (key, title, lo_txt, hi_txt) in zip(axes.flat, TRAITS):
        style(ax)
        pts = []
        for n in names:
            t = models[n]["traits"].get(key) or {}
            pts.append((t.get("score"), *domain_range(t)))
        draw_rows(ax, names, pts)
        ax.set_title(title, loc="left", fontsize=11, color=INK, fontweight="bold")
        ax.set_xlabel(f"1 = {lo_txt}    ·    9 = {hi_txt}", fontsize=8, color=INK2)
    for ax in list(axes.flat)[len(TRAITS):]:
        ax.axis("off")
    fig.suptitle("Disposition by trait  (dot = trait score, bar = spread of its domains; neither end is better)",
                 x=0.01, ha="left", fontsize=10, color=INK2)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(OUT / "by_trait.png", dpi=150, facecolor=SURFACE)
    plt.close(fig)


def profiles(models):
    names = list(models)
    cols = min(3, max(1, len(names)))
    rows = math.ceil(len(names) / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(4.6 * cols, 3.6 * rows), facecolor=SURFACE, squeeze=False)
    labels = [t[1] for t in TRAITS]
    for ax, n in zip(axes.flat, names):
        style(ax)
        pts = [(models[n]["traits"].get(k, {}).get("score"), *domain_range(models[n]["traits"].get(k, {})))
               for k, *_ in TRAITS]
        draw_rows(ax, labels, pts)
        ax.set_title(n, loc="left", fontsize=11, color=INK, fontweight="bold")
    for ax in list(axes.flat)[len(names):]:
        ax.axis("off")
    fig.suptitle("Disposition profiles, one panel per model", x=0.01, ha="left", fontsize=10, color=INK2)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(OUT / "profiles.png", dpi=150, facecolor=SURFACE)
    plt.close(fig)


def table(models):
    head = "| model | " + " | ".join(t[1] for t in TRAITS) + " | judge | submission |"
    rows = [head, "|---|" + "---|" * len(TRAITS) + "---|---|"]
    for n, m in models.items():
        cells = []
        for k, *_ in TRAITS:
            v = (m["traits"].get(k) or {}).get("score")
            cells.append("n/a" if v is None else f"{v:g}")
        rows.append(f"| {n} | " + " | ".join(cells) + f" | {m.get('judge') or ''} | `{m['submission']}` |")
    return "\n".join(rows) + "\n"


def main():
    OUT.mkdir(exist_ok=True)
    models = latest_per_model()
    if not models:
        raise SystemExit("no submissions yet")
    by_trait(models)
    profiles(models)
    md = table(models)
    (OUT / "table.md").write_text(md)
    readme = ROOT / "README.md"
    r = readme.read_text()
    r = re.sub(r"(<!-- RESULTS -->\n).*?(<!-- /RESULTS -->)", lambda m: m.group(1) + md + m.group(2), r, flags=re.S)
    readme.write_text(r)
    print(f"{len(models)} models -> charts/")


if __name__ == "__main__":
    main()
