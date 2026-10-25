"""Needle In A Haystack (NIAH) & Real-Document Benchmark Suite.

Scientifically evaluates and compares retrieval accuracy across context positions
(0% to 100% depth) and real-world documents between Baseline Sequential Context
and Position-Aware Context Optimization.

Features:
- Decoy & Distractor Needles (detects keyword-pattern stumbling vs genuine attention)
- Multi-Hop 2-Fact Synthesis mode
- Pluggable Retrieval Engines (BM25 Lexical vs SentenceTransformer Semantic)
- Real-World Document Corpus (Aerospace, Legal SLA, ICU Medical, SEC 10-K, Quantum)
- 4-Arm Architectural Ablation (Baseline vs U-Curve Only vs Sandwich Only vs Full Pipeline)
- Strict Distractor Trap Rejection
- Cost, Token Overhead & CPU Latency Accounting
"""

import argparse
import json
import os
import random
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.dispatcher import UCurveDispatcher, build_baseline_prompt, build_sandwich_prompt
from src.llm_client import LLMClient
from src.real_documents import REAL_DOCUMENTS
from src.scorer import BM25Scorer
from src.semantic_scorer import SemanticScorer

HAYSTACK_BANK = [
    "Machine learning models rely on statistical distributions to extrapolate patterns from raw observations. High-dimensional vector spaces allow mathematical representations of semantic syntax across varied domains.",
    "The history of operating systems evolved from batch processing in mainframes to interactive time-sharing systems. Modern kernels implement virtual memory subsystems with multi-level page tables to isolate processes.",
    "Distributed consensus algorithms like Paxos and Raft ensure state machine replication across unreliable networks. Fault-tolerant state machines handle network partitions while guaranteeing linearizability.",
    "Relational databases utilize B-tree indexes for logarithmic lookup complexities and write-ahead logging (WAL) to preserve atomicity and durability under unexpected hardware failures.",
    "Modern compilers utilize intermediate representations such as LLVM IR to perform target-independent optimizations including dead code elimination, constant propagation, and loop vectorization.",
    "Graph theory algorithms such as Dijkstra and Bellman-Ford provide shortest path routing in packet-switched communication networks, accounting for edge weight variations and topology changes.",
    "Cryptographic hash functions like SHA-256 provide collision resistance and pre-image resistance, forming foundational building blocks for verifiable ledger systems and message authentication.",
    "Microservices architectures decouple monolithic applications into independently deployable services communicating over lightweight RPC protocols such as gRPC or RESTful JSON interfaces.",
    "Cache coherence protocols such as MESI maintain consistency among multiple private processor caches in symmetric multiprocessing architectures, preventing dirty reads and memory divergence.",
    "Quantum computing leverages superposition and entanglement to execute probabilistic Shor's algorithm for prime factorization and Grover's algorithm for unstructured database search.",
]


def estimate_tokens(text: str) -> int:
    """Estimates token count using standard subword heuristic (1.33 tokens per whitespace word)."""
    words = len(text.split())
    return max(1, int(words * 1.33))


def generate_haystack(num_chunks: int) -> List[str]:
    """Generates synthetic background distractor chunks."""
    haystack = []
    while len(haystack) < num_chunks:
        sample = random.choice(HAYSTACK_BANK)
        haystack.append(f"{sample} (Segment ID #{len(haystack) + 1})")
    return haystack


def run_single_synthetic_trial(
    llm: LLMClient,
    scorer: Any,
    total_chunks: int,
    needle_depth: float,
    with_distractor: bool = True,
    multi_hop: bool = False,
) -> Dict[str, Any]:
    """Runs a single synthetic NIAH trial across all 4 architectural arms."""
    secret_code = f"ALPHA_{random.randint(1000, 9999)}"
    decoy_code = f"BETA_{random.randint(1000, 9999)}" if with_distractor else None

    haystack = generate_haystack(total_chunks)

    # 1. Needle Insertion
    insert_idx = int(round(needle_depth * (total_chunks - 1)))
    insert_idx = max(0, min(insert_idx, total_chunks - 1))

    if multi_hop:
        sector_id = f"SEC-{random.randint(10, 99)}"
        decoy_sector = f"SEC-{random.randint(10, 99)}"
        query = "What is the confidential security clearance passcode for the orbital propulsion subsystem?"
        # Fact 1 (Bridge Fact) placed at a different random slot
        bridge_idx = (insert_idx + total_chunks // 2) % total_chunks
        haystack[bridge_idx] = f"OPERATIONAL NOTE: The orbital propulsion subsystem is assigned exclusively to {sector_id}."
        # Fact 2 (Target Needle)
        haystack[insert_idx] = f"CRITICAL NOTICE: The confidential security clearance passcode for {sector_id} is {secret_code}."
        # Decoy Needle
        if with_distractor:
            decoy_idx = 0 if insert_idx >= total_chunks // 2 else total_chunks - 1
            if decoy_idx == bridge_idx or decoy_idx == insert_idx:
                decoy_idx = (insert_idx + 2) % total_chunks
            haystack[decoy_idx] = f"ROUTINE LOG: The confidential security clearance passcode for {decoy_sector} is {decoy_code}."
    else:
        query = "What is the confidential security clearance passcode?"
        haystack[insert_idx] = f"CRITICAL NOTICE: The confidential security clearance passcode is {secret_code}."
        if with_distractor:
            # Place decoy in primacy (Slot 0/1) or recency (Slot N-1) to test if baseline gets distracted
            decoy_idx = 0 if insert_idx >= total_chunks // 2 else total_chunks - 1
            haystack[decoy_idx] = f"Decoy backup test access passcode {decoy_code} was recorded during ground checkout."

    # 2. Latency & Token Accounting
    t_score_start = time.perf_counter()
    scored_chunks = scorer.rank_chunks(query, haystack)
    score_latency_ms = (time.perf_counter() - t_score_start) * 1000

    t_reorder_start = time.perf_counter()
    reordered_chunks = UCurveDispatcher.reorder(
        scored_chunks, score_key="score", reverse_scores=True
    )
    reorder_latency_ms = (time.perf_counter() - t_reorder_start) * 1000
    reordered_texts = [c["content"] for c in reordered_chunks]

    # 3. Assemble 4 Prompts
    baseline_prompt = build_baseline_prompt(query, haystack)
    ucurve_only_prompt = build_baseline_prompt(query, reordered_texts)
    sandwich_only_prompt = build_sandwich_prompt(query, haystack)
    full_prompt = build_sandwich_prompt(query, reordered_texts)

    base_tokens = estimate_tokens(baseline_prompt)
    sand_tokens = estimate_tokens(full_prompt)
    overhead_tokens = sand_tokens - base_tokens
    overhead_pct = round((overhead_tokens / max(1, base_tokens)) * 100, 1)

    # 4. Execute 4 Arms
    base_resp = llm.generate(baseline_prompt)
    u_only_resp = llm.generate(ucurve_only_prompt)
    sand_only_resp = llm.generate(sandwich_only_prompt)
    full_resp = llm.generate(full_prompt)

    # 5. Strict Verification: Target present AND Decoy NOT present
    def verify(resp: str) -> Tuple[bool, bool]:
        r_lower = resp.lower()
        has_target = secret_code.lower() in r_lower
        decoy_pattern = r"(?<![0-9A-Za-z])" + re.escape(decoy_code) + r"(?![0-9A-Za-z])" if decoy_code else None
        has_decoy = bool(re.search(decoy_pattern, resp, re.IGNORECASE)) if decoy_pattern else False
        is_fail_msg = "baseline retrieval failed" in r_lower
        success = has_target and not has_decoy and not is_fail_msg
        distractor_trap = has_decoy and not has_target
        return success, distractor_trap

    b_ok, b_trap = verify(base_resp)
    u_ok, u_trap = verify(u_only_resp)
    s_ok, s_trap = verify(sand_only_resp)
    f_ok, f_trap = verify(full_resp)

    return {
        "depth": needle_depth,
        "chunk_count": total_chunks,
        "secret_code": secret_code,
        "decoy_code": decoy_code,
        "baseline_success": b_ok,
        "baseline_trap": b_trap,
        "ucurve_only_success": u_ok,
        "sandwich_only_success": s_ok,
        "full_pipeline_success": f_ok,
        "score_latency_ms": round(score_latency_ms, 3),
        "reorder_latency_ms": round(reorder_latency_ms, 3),
        "baseline_tokens": base_tokens,
        "sandwich_tokens": sand_tokens,
        "token_overhead": overhead_tokens,
        "token_overhead_pct": overhead_pct,
    }


def run_single_real_doc_trial(
    llm: LLMClient,
    scorer: Any,
    doc_key: str,
    doc_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Runs a trial on a real-world document with vocabulary mismatch and domain distractors."""
    paragraphs = list(doc_data["paragraphs"])
    query = doc_data["question"]
    target_code = doc_data["target_code"]
    decoy_code = doc_data["decoy_code"]

    t_score_start = time.perf_counter()
    scored_chunks = scorer.rank_chunks(query, paragraphs)
    score_latency_ms = (time.perf_counter() - t_score_start) * 1000

    t_reorder_start = time.perf_counter()
    reordered_chunks = UCurveDispatcher.reorder(
        scored_chunks, score_key="score", reverse_scores=True
    )
    reorder_latency_ms = (time.perf_counter() - t_reorder_start) * 1000
    reordered_texts = [c["content"] for c in reordered_chunks]

    baseline_prompt = build_baseline_prompt(query, paragraphs)
    ucurve_only_prompt = build_baseline_prompt(query, reordered_texts)
    sandwich_only_prompt = build_sandwich_prompt(query, paragraphs)
    full_prompt = build_sandwich_prompt(query, reordered_texts)

    base_tokens = estimate_tokens(baseline_prompt)
    sand_tokens = estimate_tokens(full_prompt)
    overhead_tokens = sand_tokens - base_tokens
    overhead_pct = round((overhead_tokens / max(1, base_tokens)) * 100, 1)

    base_resp = llm.generate(baseline_prompt)
    u_only_resp = llm.generate(ucurve_only_prompt)
    sand_only_resp = llm.generate(sandwich_only_prompt)
    full_resp = llm.generate(full_prompt)

    def verify(resp: str) -> Tuple[bool, bool]:
        r_lower = resp.lower()
        has_target = target_code.lower() in r_lower
        decoy_pattern = r"(?<![0-9A-Za-z])" + re.escape(decoy_code) + r"(?![0-9A-Za-z])" if decoy_code else None
        has_decoy = bool(re.search(decoy_pattern, resp, re.IGNORECASE)) if decoy_pattern else False
        is_fail_msg = "baseline retrieval failed" in r_lower
        success = has_target and not has_decoy and not is_fail_msg
        distractor_trap = has_decoy and not has_target
        return success, distractor_trap

    b_ok, b_trap = verify(base_resp)
    u_ok, u_trap = verify(u_only_resp)
    s_ok, s_trap = verify(sand_only_resp)
    f_ok, f_trap = verify(full_resp)

    # Check if target paragraph was correctly identified by the scorer at Rank 1
    target_idx = doc_data.get("target_paragraph_index", -1)
    scorer_rank1_idx = scored_chunks[0]["original_index"] if scored_chunks else -1
    scorer_correct = (target_idx == scorer_rank1_idx)

    return {
        "doc_key": doc_key,
        "title": doc_data["title"],
        "domain": doc_data["domain"],
        "chunk_count": len(paragraphs),
        "target_code": target_code,
        "decoy_code": decoy_code,
        "scorer_rank1_correct": scorer_correct,
        "baseline_success": b_ok,
        "baseline_trap": b_trap,
        "ucurve_only_success": u_ok,
        "sandwich_only_success": s_ok,
        "full_pipeline_success": f_ok,
        "score_latency_ms": round(score_latency_ms, 3),
        "reorder_latency_ms": round(reorder_latency_ms, 3),
        "baseline_tokens": base_tokens,
        "sandwich_tokens": sand_tokens,
        "token_overhead": overhead_tokens,
        "token_overhead_pct": overhead_pct,
    }


def run_benchmark(
    provider: str = "mock",
    api_key: Optional[str] = None,
    scorer_type: str = "bm25",
    dataset: str = "synthetic",
    depths: Optional[List[float]] = None,
    chunk_counts: Optional[List[int]] = None,
    trials_per_step: int = 5,
    with_distractor: bool = True,
    multi_hop: bool = False,
) -> Dict[str, Any]:
    """Main benchmark execution harness."""
    llm = LLMClient(provider=provider, api_key=api_key)

    if scorer_type == "semantic":
        scorer = SemanticScorer()
        scorer_name = "Dense SentenceTransformer (all-MiniLM-L6-v2)"
    else:
        scorer = BM25Scorer()
        scorer_name = "Lexical BM25 (Robertson-Spärck Jones)"

    print("\n" + "=" * 80)
    print(f" [BENCHMARK] Position-Aware Context Optimization vs. Baseline")
    print(f" Provider: {provider.upper()} | Scorer: {scorer_name}")
    print(f" Dataset: {dataset.upper()} | Distractors: {with_distractor} | Multi-Hop: {multi_hop}")
    print(f" Trials/Step: {trials_per_step}")
    print("=" * 80)

    results: Dict[str, Any] = {
        "metadata": {
            "provider": provider,
            "scorer": scorer_type,
            "scorer_name": scorer_name,
            "dataset": dataset,
            "with_distractor": with_distractor,
            "multi_hop": multi_hop,
            "trials_per_step": trials_per_step,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "cost_latency_accounting": {},
        "by_depth": {},
        "matrix": [],
    }

    all_score_latencies = []
    all_reorder_latencies = []
    all_base_tokens = []
    all_sand_tokens = []

    if dataset == "synthetic":
        depths = depths or [0.0, 0.2, 0.4, 0.5, 0.6, 0.8, 1.0]
        chunk_counts = chunk_counts or [10, 20]

        print(f"\n{'Depth':<8} | {'Baseline':<10} | {'U-Curve Only':<14} | {'Sandwich Only':<14} | {'Full (Ours)':<12} | {'Decoy Trap %':<12}")
        print("-" * 80)

        for depth in depths:
            depth_str = f"{int(depth * 100)}%"
            b_hits = u_hits = s_hits = f_hits = trap_hits = total_evals = 0

            for count in chunk_counts:
                for trial_idx in range(trials_per_step):
                    res = run_single_synthetic_trial(
                        llm, scorer, count, depth, with_distractor, multi_hop
                    )
                    results["matrix"].append(res)
                    total_evals += 1

                    if res["baseline_success"]:
                        b_hits += 1
                    if res["baseline_trap"]:
                        trap_hits += 1
                    if res["ucurve_only_success"]:
                        u_hits += 1
                    if res["sandwich_only_success"]:
                        s_hits += 1
                    if res["full_pipeline_success"]:
                        f_hits += 1

                    all_score_latencies.append(res["score_latency_ms"])
                    all_reorder_latencies.append(res["reorder_latency_ms"])
                    all_base_tokens.append(res["baseline_tokens"])
                    all_sand_tokens.append(res["sandwich_tokens"])

            b_acc = round((b_hits / total_evals) * 100, 1)
            u_acc = round((u_hits / total_evals) * 100, 1)
            s_acc = round((s_hits / total_evals) * 100, 1)
            f_acc = round((f_hits / total_evals) * 100, 1)
            trap_rate = round((trap_hits / total_evals) * 100, 1)

            results["by_depth"][depth_str] = {
                "depth": depth,
                "baseline_acc": b_acc,
                "ucurve_only_acc": u_acc,
                "sandwich_only_acc": s_acc,
                "ucurve_acc": f_acc,  # Backwards-compatible key for visualize.py
                "full_pipeline_acc": f_acc,
                "decoy_trap_rate": trap_rate,
                "net_gain": round(f_acc - b_acc, 1),
            }

            print(
                f"{depth_str:<8} | {b_acc:>8.1f}% | {u_acc:>12.1f}% | {s_acc:>12.1f}% | {f_acc:>10.1f}% | {trap_rate:>10.1f}%"
            )

    else:
        # Real-World Document Evaluation
        print(f"\n{'Document':<30} | {'Domain':<18} | {'Scorer R1':<10} | {'Base Acc':<9} | {'Full Acc':<9} | {'Trap %':<8}")
        print("-" * 94)

        for doc_key, doc_data in REAL_DOCUMENTS.items():
            b_hits = u_hits = s_hits = f_hits = trap_hits = total_evals = 0
            scorer_r1_hits = 0

            for trial_idx in range(trials_per_step):
                res = run_single_real_doc_trial(llm, scorer, doc_key, doc_data)
                results["matrix"].append(res)
                total_evals += 1

                if res["baseline_success"]:
                    b_hits += 1
                if res["baseline_trap"]:
                    trap_hits += 1
                if res["ucurve_only_success"]:
                    u_hits += 1
                if res["sandwich_only_success"]:
                    s_hits += 1
                if res["full_pipeline_success"]:
                    f_hits += 1
                if res["scorer_rank1_correct"]:
                    scorer_r1_hits += 1

                all_score_latencies.append(res["score_latency_ms"])
                all_reorder_latencies.append(res["reorder_latency_ms"])
                all_base_tokens.append(res["baseline_tokens"])
                all_sand_tokens.append(res["sandwich_tokens"])

            b_acc = round((b_hits / total_evals) * 100, 1)
            u_acc = round((u_hits / total_evals) * 100, 1)
            s_acc = round((s_hits / total_evals) * 100, 1)
            f_acc = round((f_hits / total_evals) * 100, 1)
            trap_rate = round((trap_hits / total_evals) * 100, 1)
            scorer_acc = round((scorer_r1_hits / total_evals) * 100, 1)

            results["by_depth"][doc_key] = {
                "title": doc_data["title"],
                "domain": doc_data["domain"],
                "scorer_rank1_acc": scorer_acc,
                "baseline_acc": b_acc,
                "ucurve_only_acc": u_acc,
                "sandwich_only_acc": s_acc,
                "ucurve_acc": f_acc,  # Backwards-compatible key for visualize.py
                "full_pipeline_acc": f_acc,
                "decoy_trap_rate": trap_rate,
                "net_gain": round(f_acc - b_acc, 1),
            }

            short_title = (doc_data["title"][:28] + "..") if len(doc_data["title"]) > 30 else doc_data["title"]
            print(
                f"{short_title:<30} | {doc_data['domain'][:18]:<18} | {scorer_acc:>8.1f}% | {b_acc:>7.1f}% | {f_acc:>7.1f}% | {trap_rate:>6.1f}%"
            )

    # Compute Global Cost & Latency Accounting
    mean_score_lat = round(sum(all_score_latencies) / max(1, len(all_score_latencies)), 2)
    mean_reorder_lat = round(sum(all_reorder_latencies) / max(1, len(all_reorder_latencies)), 2)
    total_cpu_lat = round(mean_score_lat + mean_reorder_lat, 2)
    mean_base_tok = int(sum(all_base_tokens) / max(1, len(all_base_tokens)))
    mean_sand_tok = int(sum(all_sand_tokens) / max(1, len(all_sand_tokens)))
    mean_overhead_tok = mean_sand_tok - mean_base_tok
    overhead_pct = round((mean_overhead_tok / max(1, mean_base_tok)) * 100, 1)

    # Standard cloud pricing: ~$0.15 per 1,000,000 input tokens (Gemini 1.5 Flash / Groq Llama 3.3)
    cost_per_query_usd = (mean_sand_tok / 1_000_000) * 0.15
    cost_per_1k_usd = round(cost_per_query_usd * 1000, 5)

    results["cost_latency_accounting"] = {
        "mean_scoring_latency_ms": mean_score_lat,
        "mean_reordering_latency_ms": mean_reorder_lat,
        "total_preprocessing_latency_ms": total_cpu_lat,
        "mean_baseline_tokens": mean_base_tok,
        "mean_sandwich_tokens": mean_sand_tok,
        "mean_token_overhead": mean_overhead_tok,
        "mean_token_overhead_pct": overhead_pct,
        "estimated_api_cost_per_1k_queries_usd": cost_per_1k_usd,
    }

    print("\n" + "=" * 80)
    print(" [ACCOUNTING] COST, LATENCY & OVERHEAD ACCOUNTING")
    print("=" * 80)
    print(f" * Retrieval Scoring Latency:    {mean_score_lat:>6.2f} ms ({scorer_name})")
    print(f" * Two-Pointer Reorder Latency:   {mean_reorder_lat:>6.2f} ms (Pure CPU arithmetic)")
    print(f" * Total Preprocessing Overhead: {total_cpu_lat:>6.2f} ms")
    print(f" * Mean Baseline Prompt Tokens:  {mean_base_tok:>6} tokens")
    print(f" * Mean Sandwich Prompt Tokens:  {mean_sand_tok:>6} tokens")
    print(f" * Token Overhead for Anchoring: +{mean_overhead_tok} tokens (+{overhead_pct}%)")
    print(f" * Estimated API Cost:           ${cost_per_1k_usd:.5f} per 1,000 queries (@ $0.15/1M tokens)")
    print("=" * 80 + "\n")

    return results


def main():
    parser = argparse.ArgumentParser(description="Position-Aware Context Optimization Benchmark")
    parser.add_argument("--provider", type=str, default="mock", choices=["mock", "groq", "gemini"])
    parser.add_argument("--api-key", type=str, default=None, help="Cloud API key for Groq or Gemini")
    parser.add_argument("--scorer", type=str, default="bm25", choices=["bm25", "semantic"], help="Scorer strategy")
    parser.add_argument("--dataset", type=str, default="synthetic", choices=["synthetic", "real"], help="Dataset")
    parser.add_argument("--trials", type=int, default=3, help="Number of trials per depth or document")
    parser.add_argument("--no-distractor", action="store_true", help="Disable distractor/decoy needles")
    parser.add_argument("--multi-hop", action="store_true", help="Enable 2-fact multi-hop needle testing")
    parser.add_argument("--output", type=str, default="benchmark_results.json", help="Output JSON path")
    args = parser.parse_args()

    results = run_benchmark(
        provider=args.provider,
        api_key=args.api_key,
        scorer_type=args.scorer,
        dataset=args.dataset,
        trials_per_step=args.trials,
        with_distractor=not args.no_distractor,
        multi_hop=args.multi_hop,
    )

    out_path = os.path.join(os.path.dirname(__file__), args.output)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"[OK] Full benchmark results saved to: {out_path}")
    print("Run 'python visualize.py' to generate updated visual accuracy plots.")


if __name__ == "__main__":
    main()
