"""Core Context Optimization Engine: U-Curve Dispatcher and Query Anchoring.

Mitigates the 'Lost in the Middle' position bias in LLMs by strategically placing
high-relevance information at prompt extremities (primacy and recency zones),
and burying low-relevance/noise data in the attention dead-zone (middle).
"""

from typing import Any, Callable, Dict, List, Optional, Union


class UCurveDispatcher:
    """Reorders retrieved context chunks into a U-shaped distribution to maximize LLM attention."""

    @staticmethod
    def reorder(
        chunks: List[Any],
        score_key: Optional[Union[str, Callable[[Any], float]]] = None,
        reverse_scores: bool = True,
    ) -> List[Any]:
        """Reorders items such that highest scored items are placed at outer boundaries."""
        if not chunks:
            return []

        n = len(chunks)
        if n <= 2:
            return list(chunks)

        if score_key is not None:
            if callable(score_key):
                sorted_chunks = sorted(chunks, key=score_key, reverse=reverse_scores)
            elif isinstance(score_key, str):
                sorted_chunks = sorted(
                    chunks,
                    key=lambda x: x[score_key] if isinstance(x, dict) else getattr(x, score_key),
                    reverse=reverse_scores,
                )
            else:
                sorted_chunks = list(chunks)
        else:
            sorted_chunks = list(chunks)

        reordered: List[Optional[Any]] = [None] * n
        left = 0
        right = n - 1

        for i, chunk in enumerate(sorted_chunks):
            if i % 2 == 0:
                reordered[right] = chunk
                right -= 1
            else:
                reordered[left] = chunk
                left += 1

        return [item for item in reordered if item is not None]


def build_sandwich_prompt(
    query: str,
    chunks: List[str],
    system_instruction: Optional[str] = None,
    chunk_separator: str = "\n\n---\n\n",
) -> str:
    """Builds a Sandwich Prompt anchoring query at both top and bottom."""
    sys_part = f"{system_instruction.strip()}\n\n" if system_instruction else ""
    context_body = chunk_separator.join(
        f"[Document Excerpt {i+1}]:\n{chunk.strip()}" for i, chunk in enumerate(chunks)
    )

    prompt = (
        f"{sys_part}"
        f"QUESTION / INQUIRY:\n{query.strip()}\n\n"
        f"RELEVANT CONTEXT INFORMATION:\n"
        f"{context_body}\n\n"
        f"INSTRUCTION:\n"
        f"Based strictly on the provided context excerpts above, provide a concise and factual answer to the following question. "
        f"If the answer is found in any excerpt, state it explicitly.\n\n"
        f"REPEATED QUESTION: {query.strip()}\n"
        f"FINAL ANSWER:"
    )
    return prompt


def build_baseline_prompt(
    query: str,
    chunks: List[str],
    system_instruction: Optional[str] = None,
    chunk_separator: str = "\n\n---\n\n",
) -> str:
    """Builds standard sequential baseline prompt."""
    sys_part = f"{system_instruction.strip()}\n\n" if system_instruction else ""
    context_body = chunk_separator.join(
        f"[Document Excerpt {i+1}]:\n{chunk.strip()}" for i, chunk in enumerate(chunks)
    )

    prompt = (
        f"{sys_part}"
        f"CONTEXT INFORMATION:\n"
        f"{context_body}\n\n"
        f"Question: {query.strip()}\n"
        f"Answer:"
    )
    return prompt
