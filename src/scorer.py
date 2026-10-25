"""Lightweight, pure-Python CPU relevance scoring module.

Implements Robertson-Spärck Jones BM25 retrieval without requiring
heavy C-extensions, PyTorch, or GPU dependencies.
"""

import math
import re
from typing import Any, Dict, List


def tokenize(text: str) -> List[str]:
    """Tokenizes a string into lowercased word tokens."""
    return re.findall(r"\b\w+\b", text.lower())


class BM25Scorer:
    """Pure-Python BM25 retrieval scorer for ranking context chunks."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b

    def rank_chunks(
        self, query: str, chunks: List[str]
    ) -> List[Dict[str, Any]]:
        """Scores and ranks chunks against a query."""
        if not chunks:
            return []

        query_tokens = tokenize(query)
        if not query_tokens:
            return [
                {
                    "id": i,
                    "content": chunk,
                    "score": 0.0,
                    "original_index": i,
                    "rank": i + 1,
                }
                for i, chunk in enumerate(chunks)
            ]

        # Tokenize all chunks
        tokenized_corpus = [tokenize(c) for c in chunks]
        corpus_size = len(tokenized_corpus)
        doc_lengths = [len(doc) for doc in tokenized_corpus]
        avg_doc_len = sum(doc_lengths) / corpus_size if corpus_size > 0 else 1.0

        # Calculate Document Frequencies (DF)
        df: Dict[str, int] = {}
        for token in set(query_tokens):
            df[token] = sum(1 for doc in tokenized_corpus if token in doc)

        # Calculate IDF
        idf: Dict[str, float] = {}
        for token, count in df.items():
            idf[token] = math.log(1.0 + (corpus_size - count + 0.5) / (count + 0.5))

        # Score chunks
        scored_chunks: List[Dict[str, Any]] = []
        for i, (chunk, doc_tokens, doc_len) in enumerate(
            zip(chunks, tokenized_corpus, doc_lengths)
        ):
            tf: Dict[str, int] = {}
            for token in doc_tokens:
                tf[token] = tf.get(token, 0) + 1

            score = 0.0
            len_norm = 1.0 - self.b + self.b * (doc_len / (avg_doc_len or 1.0))
            for q_term in query_tokens:
                if q_term in tf:
                    term_freq = tf[q_term]
                    numerator = term_freq * (self.k1 + 1.0)
                    denominator = term_freq + self.k1 * len_norm
                    score += idf.get(q_term, 0.0) * (numerator / denominator)

            scored_chunks.append({
                "id": i,
                "content": chunk,
                "score": round(score, 4),
                "original_index": i,
            })

        # Sort descending by score
        scored_chunks.sort(key=lambda x: x["score"], reverse=True)

        for rank, item in enumerate(scored_chunks, 1):
            item["rank"] = rank

        return scored_chunks
