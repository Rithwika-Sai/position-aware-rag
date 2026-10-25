# Position-Aware Context Optimization for Long-Context LLMs

> **A zero-GPU optimization layer and benchmark suite designed to eliminate the "Lost in the Middle" position bias in Large Language Models.**

---

## 📌 Problem Overview & Empirical Grounding

Modern Large Language Models (LLMs) advertise context windows from 32k to 1M+ tokens. However, empirical studies (*Liu et al., Stanford & UC Berkeley, 2023: "Lost in the Middle: How Language Models Use Long Contexts"*) prove that retrieval accuracy follows a **U-shaped curve**:
- Information at the **beginning** of the prompt is retained (Primacy Bias).
- Information at the **end** of the prompt is retained (Recency Bias).
- Information in the **middle 40%** of the context collapses to **10%–20% accuracy** due to Rotary Position Embedding (RoPE) decay and Softmax denominator dilution.

### ⚠️ Common Benchmark Vulnerabilities Addressed:
1. **Keyword Uniqueness Artifacts:** Standard NIAH benchmarks test a single unique string without competing wrong answers. We introduced **Adversarial Decoys** (e.g. `BETA_7777` vs `ALPHA_4921`) and **Multi-Hop 2-fact linking** to test true position attention rather than simple keyword stumbling.
2. **Vocabulary Mismatch:** Pure lexical matchers (BM25) fail when queries and documents use synonyms. We added a **CPU-Only SentenceTransformer (`all-MiniLM-L6-v2`)** to evaluate semantic vector retrieval alongside lexical BM25.
3. **Ecological Validity:** Evaluated on both synthetic haystacks and **5 Real-World Domain Corpora** (Aerospace, Legal Cloud SLAs, Clinical ICU Care, SEC 10-K Accounting, Quantum Computing).
4. **Cost & Latency Transparency:** Measured microsecond CPU latencies, prompt token overhead (+10% to +17%), and exact API costs ($0.07–$0.09 per 1,000 queries).

---

## 🚀 The 4 Architectural Pillars

1. **Two-Pointer U-Curve Position Dispatcher**:
   Instead of feeding ranked chunks sequentially ($C_1 \to C_2 \to C_3 \to \dots$), our two-pointer interleaving algorithm maps ranked items into a U-shaped distribution:
   $$\text{Final Slots}: [C_2, C_4, \dots, C_{\text{lowest}}, \dots, C_3, C_1]$$
   - **Rank 1 (Most Critical Fact)** is placed at the terminal slot ($n-1$) to maximize recency attention immediately prior to generation.
   - **Rank 2** is placed at Slot 0 to capture primacy attention.
   - **Lowest Ranks (Noise / Background)** are deliberately relegated to the center "dead-zone".

2. **Dual Query Anchoring ("Sandwich Prompting")**:
   The query is injected as a semantic anchor both at the top (priming attention heads) and at the terminal end (re-activating attention immediately before the output trigger).

3. **Pluggable Dual Retrieval Engines (Zero-GPU)**:
   - **Lexical BM25 (Robertson-Spärck Jones):** $k_1=1.5, b=0.75$, scoring in $<0.5\text{ ms}$ on standard CPU.
   - **Dense Semantic Embeddings (`all-MiniLM-L6-v2`):** Resolves vocabulary mismatch with zero GPU requirement, scoring in $\approx 2.3\text{ s}$ on standard CPU.

4. **Live 4-Way Architectural Ablation Matrix**:
   Isolates the individual and synergistic contributions of each architectural component:
   - **1. Baseline Sequential** (~15% accuracy, 100% decoy trap rate in dead-zone)
   - **2. U-Curve Only** (~80% accuracy, spatial relocation)
   - **3. Sandwich Only** (~85% accuracy, query attention persistence)
   - **4. Full Proposed Pipeline** (**~98.5%–100% accuracy**, synergistic optimal)

---

## 📂 Project Architecture

```text
position_aware_rag/
├── src/
│   ├── __init__.py               # Package interface
│   ├── dispatcher.py             # Two-Pointer U-Curve Interleaving & Sandwich Prompt Engine
│   ├── scorer.py                 # Pure-Python BM25 Relevance Scorer (k1, b configurable)
│   ├── semantic_scorer.py        # SentenceTransformer (all-MiniLM-L6-v2) CPU Dense Scorer
│   ├── real_documents.py         # 5 Real-World Domain Corpora (Aerospace, Legal, Medical, etc.)
│   ├── visualizer.py             # Dynamic Attention Curves, Heatmaps & Telemetry
│   └── llm_client.py             # Unified Client (Mock LLM, Groq LLaMA-3.3, Gemini Flash)
├── benchmark.py                  # NIAH & Real-Doc Automated Benchmark Suite with Decoys & Accounting
├── visualize.py                  # Publication-ready Matplotlib 4-arm curves and real-document charts
├── app.py                        # Streamlit Interactive Web Application
├── VIVA_DEFENSE_CHEATSHEET.md    # Comprehensive defense guide & top 10 mentor Q&A
├── requirements.txt              # Python dependencies
└── README.md                     # Complete documentation
```

---

## ⚡ Benchmark Command Line Reference

### 1. Run Synthetic Multi-Depth Benchmark with Adversarial Decoys
```bash
python benchmark.py --provider mock --trials 5 --dataset synthetic
python visualize.py
```

### 2. Run Multi-Hop 2-Fact Linking Benchmark
```bash
python benchmark.py --provider mock --trials 3 --multi-hop
```

### 3. Compare BM25 Lexical vs SentenceTransformer Semantic on Real Documents
```bash
# Evaluate Lexical BM25 (fast, but susceptible to vocabulary mismatch)
python benchmark.py --provider mock --dataset real --scorer bm25

# Evaluate Dense Semantic Embeddings (resolves vocabulary mismatch on CPU)
python benchmark.py --provider mock --dataset real --scorer semantic
```

### 4. Cross-Model Validation with Real Cloud APIs
```bash
# Evaluate against Groq Cloud (LLaMA-3.3 70B)
python benchmark.py --provider groq --api-key YOUR_GROQ_API_KEY --trials 3

# Evaluate against Google Cloud (Gemini 1.5 Flash)
python benchmark.py --provider gemini --api-key YOUR_GEMINI_API_KEY --trials 3
```

---

## 📊 Empirical Findings & Latency/Cost Accounting

| Evaluation Mode | Baseline Accuracy | Full Pipeline (Ours) | Decoy Trap Rate in Dead-Zone | Preprocessing Latency | Token Overhead | Est. API Cost |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Synthetic (BM25)** | 16.7% @ 50% depth | **100.0%** | **83.3% – 100.0%** | **0.38 ms** | +57 tok (+10.0%) | $0.094 / 1k queries |
| **Real Docs (BM25)** | 20.0% average | **60.0%** (Vocab mismatch on 2 docs) | 20.0% | **0.45 ms** | +69 tok (+17.0%) | $0.071 / 1k queries |
| **Real Docs (MiniLM)**| 20.0% average | **100.0%** (100% Rank 1 retrieval) | 20.0% | **2,288 ms** (CPU) | +69 tok (+17.0%) | $0.071 / 1k queries |

---

## 🚀 Interactive Streamlit Web Demo
```bash
python -m streamlit run app.py
```
Open your browser at `http://localhost:8501`.
- Live 4-way ablation mode toggle.
- Pluggable Scorer Engine selector (BM25 vs MiniLM Dense CPU).
- Real-world document presets.
- Verifiable side-by-side prompt diff inspector.
- Real-time token overhead, RoPE distance reduction, and estimated API cost telemetry.
