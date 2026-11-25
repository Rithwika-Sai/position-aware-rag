import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches

base_dir = r"C:\Users\LENOVO\.gemini\antigravity\scratch\position_aware_rag"

# 1. Generate UI Sandbox Mockup Figure (Figure 5.1)
fig, ax = plt.subplots(figsize=(10, 4.5), dpi=300)
ax.set_xlim(0, 100)
ax.set_ylim(0, 50)
ax.axis("off")

# Window background
bg = patches.FancyBboxPatch((0, 0), 100, 50, boxstyle="round,pad=0.5", facecolor="#0e1117", edgecolor="#262730", linewidth=1.5)
ax.add_patch(bg)

# Header
ax.text(3, 45, "[Streamlit Application] Position-Aware Context Optimization", fontsize=11, fontweight="bold", color="white")
ax.text(3, 41.5, "Mitigating the 'Lost in the Middle' Effect in Long-Context LLMs", fontsize=8.5, color="#808495")

# Sidebar panel
sidebar = patches.Rectangle((2, 2), 26, 37, facecolor="#1a1c24", edgecolor="#262730", linewidth=1)
ax.add_patch(sidebar)
ax.text(4, 36, "Configuration", fontsize=10, fontweight="bold", color="white")
ax.text(4, 32, "LLM Provider:", fontsize=8.5, color="#808495")
ax.text(4, 29, "[Mock Model (Zero-GPU)]", fontsize=8, color="#00d4b2", fontweight="bold")
ax.text(4, 25, "Retrieval Scorer Engine:", fontsize=8.5, color="#808495")
ax.text(4, 22, "[BM25 (Pure CPU)]", fontsize=8, color="#00d4b2", fontweight="bold")
ax.text(4, 18, "BM25 Knobs: k1=1.5, b=0.75", fontsize=7.5, color="#808495")
ax.text(4, 14, "GPU VRAM Overhead: 0.00 MB", fontsize=7.5, color="#2ecc71", fontweight="bold")

# Main content
ax.text(32, 36, "1. Enter Context & Query", fontsize=10.5, fontweight="bold", color="white")
ax.text(32, 32.5, "Preset: [Adversarial Decoy Trap (Satellite 8 Chunks)]", fontsize=8.5, color="#f39c12", fontweight="bold")

doc_box = patches.Rectangle((32, 13), 65, 17, facecolor="#1a1c24", edgecolor="#31333f", linewidth=1)
ax.add_patch(doc_box)
ax.text(33.5, 27, "Project Apollo flight telemetry... Decoy test passcode TEST-STAGE-4401-HEX transmitted...", fontsize=7.5, color="#dcdcdc")
ax.text(33.5, 24, "Orbital trajectory stabilization thrusters fired for 12.4 seconds to counter drag...", fontsize=7.5, color="#dcdcdc")
ax.text(33.5, 21, "CRITICAL SECURITY THRESHOLD: The active operational decryption passphrase required", fontsize=7.5, color="#ff4b4b", fontweight="bold")
ax.text(33.5, 18, "to unlock emergency thrusters is ACTIVE-OMEGA-9942-SEC. Under zero circumstances...", fontsize=7.5, color="#ff4b4b", fontweight="bold")
ax.text(33.5, 15, "Radiation detection dosimeters across sensor pods recorded 0.04 mSv/hr...", fontsize=7.5, color="#dcdcdc")

# Button
btn = patches.FancyBboxPatch((32, 5), 25, 6, boxstyle="round,pad=0.3", facecolor="#ff4b4b", edgecolor="#ff4b4b")
ax.add_patch(btn)
ax.text(44.5, 7.5, "Run Comparison", fontsize=9, fontweight="bold", color="white", ha="center")

plt.tight_layout()
ui_path = os.path.join(base_dir, "fig_ui_sandbox.png")
plt.savefig(ui_path, dpi=300)
plt.close()
print(f"[OK] Saved {ui_path}")

# 2. Generate 4-Way Ablation Model Output (Figure 5.6)
fig, ax = plt.subplots(figsize=(10, 4.5), dpi=300)
ax.set_xlim(0, 100)
ax.set_ylim(0, 50)
ax.axis("off")

bg2 = patches.FancyBboxPatch((0, 0), 100, 50, boxstyle="round,pad=0.5", facecolor="#f8f9fa", edgecolor="#dee2e6", linewidth=1.5)
ax.add_patch(bg2)

ax.text(3, 45, "4-Way Architectural Component Ablation Output Comparison", fontsize=11, fontweight="bold", color="#212529")

col_w = 22.5
h = 36
y = 5

cols = [
    ("1. Baseline Sequential", "TRAPPED BY DECOY", "#f8d7da", "#721c24", "Outputs: TEST-STAGE-4401-HEX\n(Failed to recall target in\nmiddle dead-zone; deceived\nby boundary decoy)."),
    ("2. U-Curve Only", "SPATIAL RESCUE", "#fff3cd", "#856404", "Outputs: ACTIVE-OMEGA-9942-SEC\n(Target placed in recency slot;\nrescued from dead-zone,\nsusceptible to query drift)."),
    ("3. Sandwich Only", "QUERY ANCHORED", "#d1ecf1", "#0c5460", "Outputs: ACTIVE-OMEGA-9942-SEC\n(Query anchored at start & end;\ntarget still in middle trough,\npartial recall)."),
    ("4. Full Pipeline (Ours)", "100% SUCCESS", "#d4edda", "#155724", "Outputs: ACTIVE-OMEGA-9942-SEC\n(Target placed in recency slot +\ndual query anchors. Perfect\nextraction & decoy rejection!).")
]

for idx, (title, badge, bg_c, text_c, desc) in enumerate(cols):
    x = 3 + idx * (col_w + 1.8)
    card = patches.FancyBboxPatch((x, y), col_w, h, boxstyle="round,pad=0.4", facecolor=bg_c, edgecolor=text_c, linewidth=1.2)
    ax.add_patch(card)
    ax.text(x + col_w/2, 38, title, fontsize=8.5, fontweight="bold", color=text_c, ha="center")
    ax.text(x + col_w/2, 34, badge, fontsize=7.5, fontweight="bold", color="white" if "100%" in badge else text_c, ha="center",
            bbox=dict(boxstyle="round,pad=0.2", facecolor=text_c if "100%" in badge else "white", edgecolor=text_c, alpha=0.9))
    ax.text(x + 1.5, 23, desc, fontsize=7.5, color="#212529", va="center")

plt.tight_layout()
ablation_path = os.path.join(base_dir, "fig_ui_ablation_output.png")
plt.savefig(ablation_path, dpi=300)
plt.close()
print(f"[OK] Saved {ablation_path}")
