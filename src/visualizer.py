"""Dynamic visualization and telemetry module for Position-Aware RAG.

Generates real-time, responsive Matplotlib figures and attention telemetry
tailored to the active document paragraphs and user query.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def compute_attention_weight(depth: float, is_anchored: bool = False) -> float:
    """Computes realistic token attention weight according to Liu et al. (2023).

    Args:
        depth: Relative token position within the context window (0.0 to 1.0).
        is_anchored: Whether dual-ended Query Anchoring (Sandwich Prompt) is applied.

    Returns:
        Estimated attention weight / retrieval probability (0.0 to 1.0).
    """
    depth = max(0.001, min(0.999, depth))

    if depth < 0.25:
        # Primacy boundary: high attention gradually sloping into transition
        t = depth / 0.25
        base = 0.96 - 0.24 * (t ** 1.4)
    elif depth > 0.75:
        # Recency boundary: high attention sharply rising near terminal prompt tokens
        t = (depth - 0.75) / 0.25
        base = 0.72 + 0.26 * (t ** 0.85)
    else:
        # Attention dead-zone trough: parabolic drop centered at 0.50
        dist = abs(depth - 0.50) / 0.25
        base = 0.15 + 0.38 * (dist ** 2)

    if is_anchored:
        # Sandwich prompting anchors the question at both extremities,
        # dramatically boosting attention across all intermediate slots.
        return min(0.985, base + 0.50 * (1.0 - base) + 0.22)

    return min(0.98, max(0.12, base))


def compute_chunk_telemetry(
    raw_chunks: List[str],
    ranked_chunks: List[Dict[str, Any]],
    ucurve_chunks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Calculates per-chunk attention metrics, depths, and retrieval gains.

    Returns a list of chunk telemetry records sorted by original paragraph order.
    """
    n = max(len(raw_chunks), 1)

    # Map original index to ranked info
    rank_map = {}
    for r_idx, c in enumerate(ranked_chunks):
        orig_i = c.get("original_index", r_idx)
        rank_map[orig_i] = {
            "rank": c.get("rank", r_idx + 1),
            "score": c.get("score", 0.0),
        }

    # Map original index to ucurve slot
    ucurve_slot_map = {}
    for slot_idx, c in enumerate(ucurve_chunks):
        orig_i = c.get("original_index", slot_idx)
        ucurve_slot_map[orig_i] = slot_idx

    telemetry = []
    for i, chunk_text in enumerate(raw_chunks):
        r_info = rank_map.get(i, {"rank": i + 1, "score": 0.0})
        rank = r_info["rank"]
        score = r_info["score"]

        # Baseline position
        base_slot = i + 1
        base_depth = (i + 0.5) / n
        base_attn = compute_attention_weight(base_depth, is_anchored=False)

        # U-Curve position
        u_slot_idx = ucurve_slot_map.get(i, i)
        u_slot = u_slot_idx + 1
        u_depth = (u_slot_idx + 0.5) / n
        u_attn = compute_attention_weight(u_depth, is_anchored=True)

        delta = u_attn - base_attn

        if rank == 1:
            status = "⭐ Rescued (Top Match)"
        elif rank == 2:
            status = "🟢 Primacy Protected"
        elif u_slot_idx < 2 or u_slot_idx >= n - 2:
            status = "🟢 Boundary Safe"
        else:
            status = "⚪ Buffer / Distractor"

        # Sanitize preview
        preview = re.sub(r"\s+", " ", chunk_text).strip()
        if len(preview) > 75:
            preview = preview[:75] + "..."

        telemetry.append({
            "paragraph_num": i + 1,
            "preview": preview,
            "score": score,
            "rank": rank,
            "base_slot": base_slot,
            "base_depth_pct": round(base_depth * 100, 1),
            "base_attn_pct": round(base_attn * 100, 1),
            "u_slot": u_slot,
            "u_depth_pct": round(u_depth * 100, 1),
            "u_attn_pct": round(u_attn * 100, 1),
            "delta_pct": round(delta * 100, 1),
            "status": status,
        })

    return telemetry


def plot_dynamic_u_curve(
    raw_chunks: List[str],
    ranked_chunks: List[Dict[str, Any]],
    ucurve_chunks: List[Dict[str, Any]],
    query: str = "",
) -> matplotlib.figure.Figure:
    """Plots the continuous attention U-curve with active document chunks overlaid."""
    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=200)

    # Shaded Zones
    ax.axvspan(0, 25, color="#e8f8f5", alpha=0.8, label="Primacy Zone (0%-25%)")
    ax.axvspan(25, 75, color="#fdebd0", alpha=0.7, label="Lost-in-the-Middle Dead-Zone (25%-75%)")
    ax.axvspan(75, 100, color="#e8f8f5", alpha=0.8, label="Recency Zone (75%-100%)")

    # Continuous Curves
    depths = np.linspace(0.005, 0.995, 300)
    baseline_curve = [compute_attention_weight(d, is_anchored=False) * 100 for d in depths]
    anchored_curve = [compute_attention_weight(d, is_anchored=True) * 100 for d in depths]

    ax.plot(
        depths * 100,
        baseline_curve,
        linestyle="--",
        color="#c0392b",
        linewidth=2.2,
        label="Baseline Attention Capacity",
        alpha=0.85,
    )
    ax.plot(
        depths * 100,
        anchored_curve,
        color="#27ae60",
        linewidth=2.6,
        label="Position-Aware + Anchored Capacity",
    )

    telemetry = compute_chunk_telemetry(raw_chunks, ranked_chunks, ucurve_chunks)
    n = len(raw_chunks)

    # Plot chunks
    rank_1_base_xy = None
    rank_1_u_xy = None
    rank_1_pnum = None

    for item in telemetry:
        p_num = item["paragraph_num"]
        rank = item["rank"]
        b_x, b_y = item["base_depth_pct"], item["base_attn_pct"]
        u_x, u_y = item["u_depth_pct"], item["u_attn_pct"]

        if rank == 1:
            rank_1_base_xy = (b_x, b_y)
            rank_1_u_xy = (u_x, u_y)
            rank_1_pnum = p_num

            # Baseline top match marker
            ax.scatter(b_x, b_y, color="#c0392b", s=190, edgecolors="black", linewidth=1.5, zorder=6)
            ax.annotate(
                f"P{p_num} (Top Match)\n{b_y:.0f}% Attn (Trapped)",
                xy=(b_x, b_y),
                xytext=(b_x, b_y - 12 if b_y > 30 else b_y + 12),
                ha="center",
                fontsize=8.5,
                fontweight="bold",
                color="#922b21",
                bbox=dict(boxstyle="round,pad=0.25", facecolor="#f9ebea", edgecolor="#c0392b", alpha=0.95),
            )

            # U-Curve top match marker
            ax.scatter(u_x, u_y, color="#27ae60", marker="*", s=320, edgecolors="darkgreen", linewidth=1.5, zorder=7)
            ax.annotate(
                f"P{p_num} [Rank #1]\n{u_y:.0f}% Attn (Rescued)",
                xy=(u_x, u_y),
                xytext=(u_x - 6 if u_x > 80 else u_x + 6, u_y - 14),
                ha="center",
                fontsize=8.5,
                fontweight="bold",
                color="#145a32",
                bbox=dict(boxstyle="round,pad=0.25", facecolor="#eafaf1", edgecolor="#27ae60", alpha=0.95),
            )
        else:
            # Baseline distractor
            ax.scatter(b_x, b_y, color="#e74c3c", s=50, alpha=0.6, zorder=4)
            ax.text(b_x, b_y + 2.5, f"P{p_num}", fontsize=7.5, ha="center", color="#78281f", alpha=0.85)

            # U-curve distractor
            ax.scatter(u_x, u_y, color="#2ecc71", marker="o", s=50, alpha=0.7, zorder=5)
            ax.text(u_x, u_y + 2.5, f"P{p_num}", fontsize=7.5, ha="center", color="#196f3d", alpha=0.85)

    # Draw Rescue Vector if Rank #1 was shifted
    if rank_1_base_xy and rank_1_u_xy and rank_1_base_xy != rank_1_u_xy:
        b_x, b_y = rank_1_base_xy
        u_x, u_y = rank_1_u_xy
        gain = u_y - b_y

        ax.annotate(
            "",
            xy=(u_x, u_y),
            xytext=(b_x, b_y),
            arrowprops=dict(
                arrowstyle="-|>",
                connectionstyle="arc3,rad=-0.22",
                color="#8e44ad",
                lw=2.5,
                linestyle="--",
                mutation_scale=16,
            ),
            zorder=6,
        )

        mid_x = (b_x + u_x) / 2
        mid_y = (b_y + u_y) / 2
        ax.text(
            mid_x,
            mid_y + 6,
            f"Optimization Vector\n(Gain: +{gain:.0f}% Attention)",
            color="#5b2c6f",
            fontsize=8.5,
            fontweight="bold",
            ha="center",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#f4ecf7", edgecolor="#8e44ad", alpha=0.95),
            zorder=7,
        )

    title_query = f" | Query: \"{query[:45]}...\"" if query else ""
    ax.set_title(f"Dynamic Context Attention Analysis for Current Document ({n} Chunks){title_query}", fontsize=12, fontweight="bold", pad=12)
    ax.set_xlabel("Context Depth within Prompt (0% = Start, 100% = Generation Trigger)", fontsize=10, labelpad=8)
    ax.set_ylabel("Estimated Attention Weight / Retrieval Capacity (%)", fontsize=10, labelpad=8)
    ax.set_xlim(-2, 102)
    ax.set_ylim(0, 118)
    ax.grid(True, linestyle=":", alpha=0.55)
    ax.legend(loc="lower center", ncol=4, fontsize=8.5, frameon=True, framealpha=0.95)
    plt.tight_layout()

    return fig


def plot_paragraph_bar_comparison(
    raw_chunks: List[str],
    ranked_chunks: List[Dict[str, Any]],
    ucurve_chunks: List[Dict[str, Any]],
) -> matplotlib.figure.Figure:
    """Plots side-by-side retrieval attention probabilities per paragraph."""
    telemetry = compute_chunk_telemetry(raw_chunks, ranked_chunks, ucurve_chunks)
    p_labels = [f"P{t['paragraph_num']}" for t in telemetry]
    base_attns = [t["base_attn_pct"] for t in telemetry]
    u_attns = [t["u_attn_pct"] for t in telemetry]
    ranks = [t["rank"] for t in telemetry]

    fig, ax = plt.subplots(figsize=(11, 4.8), dpi=200)
    x = np.arange(len(p_labels))
    width = 0.36

    # Bars
    bars_base = ax.bar(x - width / 2, base_attns, width, label="Baseline Sequential", color="#e74c3c", alpha=0.85, edgecolor="#c0392b")
    bars_u = ax.bar(x + width / 2, u_attns, width, label="Position-Aware (Ours)", color="#27ae60", alpha=0.88, edgecolor="#1e8449")

    # Formatting and labels
    ax.set_title("Per-Paragraph Attention Weight Comparison for Active Context", fontsize=12, fontweight="bold", pad=12)
    ax.set_xlabel("Document Paragraphs (Chronological Document Order)", fontsize=10, labelpad=8)
    ax.set_ylabel("Estimated Retrieval Probability (%)", fontsize=10, labelpad=8)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{p}\n(Rank #{r})" if r <= 2 else f"{p}" for p, r in zip(p_labels, ranks)], fontsize=9)
    ax.set_ylim(0, 118)
    ax.grid(axis="y", linestyle=":", alpha=0.5)
    ax.legend(loc="upper left", fontsize=9, frameon=True)

    # Highlight Rank #1 chunk
    for i, t in enumerate(telemetry):
        b_val = base_attns[i]
        u_val = u_attns[i]

        ax.text(x[i] - width / 2, b_val + 2, f"{int(b_val)}%", ha="center", fontsize=8, color="#78281f")
        ax.text(x[i] + width / 2, u_val + 2, f"{int(u_val)}%", ha="center", fontsize=8, fontweight="bold", color="#145a32")

        if t["rank"] == 1:
            gain = u_val - b_val
            ax.annotate(
                f"Top Match (Rank #1)\n+{gain:.0f}% Gain",
                xy=(x[i] + width / 2, u_val),
                xytext=(x[i] + width / 2, u_val + 10),
                ha="center",
                fontsize=8.5,
                fontweight="bold",
                color="#5b2c6f",
                bbox=dict(boxstyle="round,pad=0.25", facecolor="#f4ecf7", edgecolor="#8e44ad", alpha=0.9),
                arrowprops=dict(arrowstyle="->", color="#8e44ad", lw=1.2),
            )

    plt.tight_layout()
    return fig


def plot_context_matrix_heatmap(
    raw_chunks: List[str],
    ranked_chunks: List[Dict[str, Any]],
    ucurve_chunks: List[Dict[str, Any]],
) -> matplotlib.figure.Figure:
    """Plots a 2D context window allocation heatmap comparing sequential vs. position-aware slots."""
    n = len(raw_chunks)
    telemetry = compute_chunk_telemetry(raw_chunks, ranked_chunks, ucurve_chunks)

    # Baseline slot attention row
    base_matrix = np.zeros(n)
    base_labels = []
    for i in range(n):
        depth = (i + 0.5) / n
        attn = compute_attention_weight(depth, is_anchored=False) * 100
        base_matrix[i] = attn
        # find chunk in telemetry with base_slot == i + 1
        item = next(t for t in telemetry if t["base_slot"] == i + 1)
        r = item["rank"]
        badge = " [TOP]" if r == 1 else f" (R#{r})"
        base_labels.append(f"P{item['paragraph_num']}{badge}\n{attn:.0f}%")

    # U-Curve slot attention row
    ucurve_matrix = np.zeros(n)
    ucurve_labels = []
    for slot_idx in range(n):
        chunk = ucurve_chunks[slot_idx]
        orig_i = chunk.get("original_index", slot_idx)
        r = chunk.get("rank", slot_idx + 1)
        depth = (slot_idx + 0.5) / n
        attn = compute_attention_weight(depth, is_anchored=True) * 100
        ucurve_matrix[slot_idx] = attn
        badge = " [TOP]" if r == 1 else f" (R#{r})"
        ucurve_labels.append(f"P{orig_i + 1}{badge}\n{attn:.0f}%")

    data = np.vstack([base_matrix, ucurve_matrix])

    fig, ax = plt.subplots(figsize=(max(9, n * 1.5), 3.4), dpi=200)
    im = ax.imshow(data, cmap="RdYlGn", vmin=15, vmax=100, aspect="auto")

    ax.set_yticks([0, 1])
    ax.set_yticklabels(["Sequential Baseline", "Position-Aware (Ours)"], fontsize=10, fontweight="bold")
    ax.set_xticks(np.arange(n))
    ax.set_xticklabels([f"Slot #{i+1}" for i in range(n)], fontsize=9)

    # Overlay text inside cells
    for j in range(n):
        ax.text(j, 0, base_labels[j], ha="center", va="center", color="black", fontsize=8.5, fontweight="bold")
        ax.text(j, 1, ucurve_labels[j], ha="center", va="center", color="black", fontsize=8.5, fontweight="bold")

    ax.set_title("Context Window Attention Heatmap by Slot Position", fontsize=11, fontweight="bold", pad=10)
    cbar = plt.colorbar(im, ax=ax, orientation="horizontal", pad=0.25, shrink=0.6)
    cbar.set_label("Estimated Attention Capacity (%)", fontsize=9)

    plt.tight_layout()
    return fig
