"""Semantic Dense Embedding Scorer using sentence-transformers (all-MiniLM-L6-v2).

Provides CPU-only dense embedding retrieval as an alternative to lexical BM25,
specifically handling vocabulary mismatch and semantic synonyms while preserving
zero-GPU capability.
"""

import os
import re
from typing import Any, Dict, List, Optional

# Prevent TensorFlow import conflicts with protobuf on Windows
os.environ["USE_TF"] = "0"
os.environ["TRANSFORMERS_NO_TF"] = "1"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"


class SemanticScorer:
    """Computes semantic similarity using all-MiniLM-L6-v2 embeddings on CPU."""

    _model = None

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name

    @classmethod
    def _get_model(cls, model_name: str = "all-MiniLM-L6-v2"):
        if cls._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                cls._model = SentenceTransformer(model_name, device="cpu")
            except Exception as e:
                cls._model = False  # Mark as unavailable
        return cls._model

    def rank_chunks(self, query: str, chunks: List[str]) -> List[Dict[str, Any]]:
        """Scores and ranks chunks against query using dense semantic embeddings."""
        if not chunks:
            return []

        if not query.strip():
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

        model = self._get_model(self.model_name)

        if model is not False and model is not None:
            return self._score_with_embeddings(model, query, chunks)
        else:
            return self._score_with_tfidf_fallback(query, chunks)

    def _score_with_embeddings(
        self, model: Any, query: str, chunks: List[str]
    ) -> List[Dict[str, Any]]:
        import numpy as np

        query_emb = model.encode(query, convert_to_numpy=True, normalize_embeddings=True)
        chunk_embs = model.encode(chunks, convert_to_numpy=True, normalize_embeddings=True)

        # Dot product of normalized vectors equals cosine similarity
        scores = np.dot(chunk_embs, query_emb)

        ranked = []
        for i, (chunk, score) in enumerate(zip(chunks, scores)):
            ranked.append(
                {
                    "id": i,
                    "content": chunk,
                    "score": round(float(score), 4),
                    "original_index": i,
                }
            )

        ranked.sort(key=lambda x: x["score"], reverse=True)
        for rank, item in enumerate(ranked, 1):
            item["rank"] = rank

        return ranked

    def _score_with_tfidf_fallback(
        self, query: str, chunks: List[str]
    ) -> List[Dict[str, Any]]:
        """Fallback to character/word n-gram TF-IDF when neural model is unavailable."""
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
        try:
            corpus = [query] + chunks
            matrix = vectorizer.fit_transform(corpus)
            query_vec = matrix[0:1]
            chunk_vecs = matrix[1:]
            sims = cosine_similarity(query_vec, chunk_vecs).flatten()
        except Exception:
            sims = [0.0] * len(chunks)

        ranked = []
        for i, (chunk, score) in enumerate(zip(chunks, sims)):
            ranked.append(
                {
                    "id": i,
                    "content": chunk,
                    "score": round(float(score), 4),
                    "original_index": i,
                }
            )

        ranked.sort(key=lambda x: x["score"], reverse=True)
        for rank, item in enumerate(ranked, 1):
            item["rank"] = rank

        return ranked
