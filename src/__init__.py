"""Position-Aware Context Optimization Package.

A zero-GPU framework to mitigate the 'Lost in the Middle' position bias in LLMs.
"""

from .dispatcher import UCurveDispatcher, build_baseline_prompt, build_sandwich_prompt
from .llm_client import LLMClient
from .real_documents import REAL_DOCUMENTS
from .scorer import BM25Scorer
from .semantic_scorer import SemanticScorer
from .visualizer import (
    compute_attention_weight,
    compute_chunk_telemetry,
    plot_context_matrix_heatmap,
    plot_dynamic_u_curve,
    plot_paragraph_bar_comparison,
)

__all__ = [
    "UCurveDispatcher",
    "build_baseline_prompt",
    "build_sandwich_prompt",
    "BM25Scorer",
    "SemanticScorer",
    "REAL_DOCUMENTS",
    "LLMClient",
    "compute_attention_weight",
    "compute_chunk_telemetry",
    "plot_dynamic_u_curve",
    "plot_paragraph_bar_comparison",
    "plot_context_matrix_heatmap",
]
