"""Visualization module for the Lost in the Middle Benchmark.

Generates publication-ready figures for:
1. Synthetic Multi-Depth Retrieval Curves (4-Arm Ablation & Decoy Trap Rate)
2. Real-World Document Evaluation across 5 Domains (Aerospace, Legal, Medical, Finance, Quantum)
3. Side-by-Side Accuracy Comparison Bar Charts
"""

import json
import os
import sys

try:
    import matplotlib.pyplot as plt
    import numpy as np
except ImportError:
    print("Error: matplotlib and numpy are required to generate visual plots.")
    print("Please install them via: pip install matplotlib numpy")
    sys.exit(1)


def generate_plots(results_file: str = "benchmark_results.json"):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(base_dir, results_file)

    if not os.path.exists(json_path):
        print(f"Warning: Results file '{json_path}' not found. Please run 'python benchmark.py' first.")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    by_depth = data.get("by_depth", {})
    metadata = data.get("metadata", {})
    dataset_type = metadata.get("dataset", "synthetic")

    if not by_depth:
        print("Error: No evaluation data found in benchmark results.")
        return

    labels = list(by_depth.keys())
    is_depth_percentages = any("%" in k for k in labels)

    baseline_accs = [by_depth[k].get("baseline_acc", 0.0) for k in labels]
    ucurve_accs = [by_depth[k].get("full_pipeline_acc", by_depth[k].get("ucurve_acc", 0.0)) for k in labels]
    u_only_accs = [by_depth[k].get("ucurve_only_acc", 0.0) for k in labels]
    s_only_accs = [by_depth[k].get("sandwich_only_acc", 0.0) for k in labels]
    trap_rates = [by_depth[k].get("decoy_trap_rate", 0.0) for k in labels]

    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")

    if is_depth_percentages:
        # --- PLOT 1: Synthetic 4-Arm Ablation & Decoy Trap Curve ---
        plt.figure(figsize=(11, 6.5), dpi=300)

        plt.plot(labels, baseline_accs, marker="o", color="#e74c3c", linewidth=2.5, label="1. Baseline Sequential", markersize=8)
        if any(u > 0 for u in u_only_accs):
            plt.plot(labels, u_only_accs, marker="^", color="#f39c12", linewidth=2.0, linestyle="--", label="2. U-Curve Only (Spatial)", markersize=7)
        if any(s > 0 for s in s_only_accs):
            plt.plot(labels, s_only_accs, marker="d", color="#3498db", linewidth=2.0, linestyle="-.", label="3. Sandwich Only (Anchors)", markersize=7)
        plt.plot(labels, ucurve_accs, marker="s", color="#2ecc71", linewidth=3.0, label="4. Full Proposed Pipeline (Ours)", markersize=9)

        if "50%" in labels:
            mid_idx = labels.index("50%")
            plt.annotate(
                "\"Lost in the Middle\"\nAttention Dead-Zone",
                xy=(mid_idx, baseline_accs[mid_idx]),
                xytext=(mid_idx - 0.4, baseline_accs[mid_idx] + 28),
                arrowprops=dict(facecolor="#e74c3c", shrink=0.08, width=1.5, headwidth=8),
                fontweight="bold",
                color="#c0392b",
                ha="center",
            )

        plt.title(f"4-Arm Architectural Retrieval Accuracy vs. Context Insertion Depth\n(Provider: {metadata.get('provider', 'mock').upper()} | Scorer: {metadata.get('scorer', 'bm25').upper()})", fontsize=13, fontweight="bold", pad=15)
        plt.xlabel("Needle Insertion Depth (% of Context Window)", fontsize=11, labelpad=10)
        plt.ylabel("Retrieval Accuracy (%)", fontsize=11, labelpad=10)
        plt.ylim(-5, 110)
        plt.legend(fontsize=10, loc="lower left", frameon=True)
        plt.grid(True, linestyle="--", alpha=0.6)
        plt.tight_layout()

        curve_path = os.path.join(base_dir, "benchmark_curve.png")
        plt.savefig(curve_path)
        plt.close()
        print(f"[OK] Accuracy curve plot saved: {curve_path}")

        # --- PLOT 2: Side-by-Side Comparison with Decoy Trap ---
        plt.figure(figsize=(12, 5.5), dpi=300)
        x = np.arange(len(labels))
        width = 0.35

        plt.bar(x - width/2, baseline_accs, width, label="Baseline Sequential", color="#e74c3c", alpha=0.85)
        plt.bar(x + width/2, ucurve_accs, width, label="Position-Aware (Ours)", color="#27ae60", alpha=0.85)

        plt.title("Baseline vs. Position-Aware Accuracy across Context Depths", fontsize=13, fontweight="bold", pad=15)
        plt.xlabel("Document Depth", fontsize=11, labelpad=10)
        plt.ylabel("Accuracy (%)", fontsize=11, labelpad=10)
        plt.xticks(x, labels)
        plt.ylim(0, 118)
        plt.legend(fontsize=10)
        plt.grid(axis="y", linestyle="--", alpha=0.5)

        for i in range(len(x)):
            plt.text(x[i] - width/2, baseline_accs[i] + 2, f"{int(baseline_accs[i])}%", ha="center", fontsize=8)
            plt.text(x[i] + width/2, ucurve_accs[i] + 2, f"{int(ucurve_accs[i])}%", ha="center", fontsize=8, fontweight="bold")

        plt.tight_layout()
        bar_path = os.path.join(base_dir, "benchmark_comparison_bar.png")
        plt.savefig(bar_path)
        plt.close()
        print(f"[OK] Comparison bar chart saved: {bar_path}")

    else:
        # Real-World Document Visualization
        clean_labels = [by_depth[k].get("domain", k[:14]) for k in labels]

        fig, ax = plt.subplots(figsize=(12, 6), dpi=300)
        x = np.arange(len(clean_labels))
        width = 0.35

        ax.bar(x - width/2, baseline_accs, width, label="Baseline Sequential", color="#e74c3c", alpha=0.85)
        ax.bar(x + width/2, ucurve_accs, width, label="Position-Aware (Ours)", color="#2ecc71", alpha=0.85)

        ax.set_title(f"Real-World Domain Evaluation across 5 Corpora\n(Provider: {metadata.get('provider', 'mock').upper()} | Scorer: {metadata.get('scorer', 'bm25').upper()})", fontsize=13, fontweight="bold", pad=15)
        ax.set_xlabel("Document Domain Corpus", fontsize=11, labelpad=10)
        ax.set_ylabel("Retrieval Accuracy (%)", fontsize=11, labelpad=10)
        ax.set_xticks(x)
        ax.set_xticklabels(clean_labels, rotation=15, ha="right", fontsize=9)
        ax.set_ylim(0, 120)
        ax.legend(fontsize=10)
        ax.grid(axis="y", linestyle="--", alpha=0.5)

        for i in range(len(x)):
            ax.text(x[i] - width/2, baseline_accs[i] + 2, f"{int(baseline_accs[i])}%", ha="center", fontsize=8)
            ax.text(x[i] + width/2, ucurve_accs[i] + 2, f"{int(ucurve_accs[i])}%", ha="center", fontsize=8, fontweight="bold")

        plt.tight_layout()
        bar_path = os.path.join(base_dir, "benchmark_comparison_bar.png")
        plt.savefig(bar_path)
        plt.close()
        print(f"[OK] Real-document comparison chart saved: {bar_path}")


if __name__ == "__main__":
    generate_plots()
