# Beacon RAG study: embeddings, chunking and retrieval

A retrieval-augmented generation (RAG) assistant over Beacon's own product documentation, built to measure how embedding size, chunking strategy and generation settings change what gets retrieved and how good the final answer is. The findings and design notes are in [rag_analysis.md](rag_analysis.md).

## Files

```text
rag-retrieval-study/
├── rag_system.ipynb        the full pipeline and every experiment
├── rag_analysis.md         results, comparisons, failure analysis, system design
├── requirements.txt
├── README.md
├── data/
│   └── beacon_knowledge_base.json
└── outputs/                written by the notebook (the reported run is included)
```

The knowledge base is 30 paragraphs (3,021 words) in 10 topic sections, each paragraph with an ID, section, topic and source label. It was written from Beacon's README, Django `models.py`, the multi-model system design and the model-selection notebook. It describes the product and data model; it contains no user data.

## Models

| Size | Embedding model | Dimensions |
|---|---|---:|
| Small | `BAAI/bge-small-en-v1.5` | 384 |
| Medium | `BAAI/bge-base-en-v1.5` | 768 |
| Large | `BAAI/bge-large-en-v1.5` | 1024 |

Three sizes from one model family (MIT licence), so size is the main thing that changes. Model cards: [small](https://huggingface.co/BAAI/bge-small-en-v1.5), [base](https://huggingface.co/BAAI/bge-base-en-v1.5), [large](https://huggingface.co/BAAI/bge-large-en-v1.5).

**Generation:** `Qwen/Qwen3-4B-Instruct-2507` ([model card](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507), Apache-2.0), the model chosen in the team's model-selection study. It is loaded with `transformers` and kept identical across all nine configurations (greedy decoding, same prompt, 220 new tokens).

**Answer-quality judge:** `nemotron-3-super-120b-a12b` on UIUC NCSA Lumen (OpenAI-compatible API), a different and much larger model than the generator, so Qwen never grades its own answers. It applies the team's answer-quality rubric against a fixed key-point checklist per question. Scores are reported as LLM-judge scores. Every verdict is cached in `outputs/answer_quality_llm_judge.csv`, so **re-running the notebook needs no key**; a key is only needed when an answer changes (for example on a different GPU, where greedy decoding can differ slightly).

## Setup

Python 3.11. Use a separate environment:

```bash
conda create -n beacon-rag python=3.11 -y
conda activate beacon-rag
```

1. **Install PyTorch for your hardware first.** On an NVIDIA GPU, pick the CUDA build from the [PyTorch selector](https://pytorch.org/get-started/locally/). On Apple Silicon the standard wheel includes MPS.
2. **Install the rest:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Check the device:**
   ```bash
   python -c "import torch; print('CUDA:', torch.cuda.is_available()); print('MPS:', torch.backends.mps.is_available())"
   ```
   With neither, the notebook runs on CPU in FP32, which is slow and needs a lot of memory for the 4B model.
4. **(Optional) judge key**, only if answers change and need new scores:
   ```bash
   export JUDGE_API_KEY="<your Lumen key>"     # LUMEN_API_KEY also works; never commit it
   # optional: JUDGE_BASE_URL, JUDGE_MODEL
   ```
5. **Run** from this folder:
   ```bash
   jupyter lab            # open rag_system.ipynb, Run All
   # or headless:
   jupyter nbconvert --to notebook --execute --inplace rag_system.ipynb
   ```

The first run downloads the three embedding models and Qwen (about 8 GB) from Hugging Face; later runs use the local cache.

## Memory

The notebook loads one embedding model at a time, keeps the generator loaded once, embeds in batches of 16, and uses FP16 on CUDA and MPS. On MPS it loads the generator on CPU and then moves it, because loading straight onto MPS crashes in recent `transformers` releases. A 24 GB Mac runs it comfortably with other heavy apps closed.

## What the notebook does

1. Validates the corpus (paragraph count, 80 to 200 words each, 2,000 to 5,000 words total).
2. Builds three chunk sets: fixed length (sentence-packed to 180 words), overlapping paragraphs (window 2, stride 1) and hybrid (whole sections up to 360 words). No chunk splits a sentence or mixes sections.
3. Embeds every chunk with each model into a normalized NumPy vector index.
4. Runs six test questions through all nine configurations (top-k 3), generating each answer with the same Qwen model.
5. Measures context recall, precision, F1 and noise against hand-labelled gold paragraphs, answer quality with the judge, and latency and tokens.
6. Compares an 18-paragraph subset with the full corpus.
7. Picks out the weakest results and tests three fixes before and after: top-k 3 to 5, splitting two-part questions, and an answer-length budget.

## Outputs

- `evaluation_results.csv`: one row per configuration and question, with metrics, answer, judge scores and latency
- `evaluation_table_with_retrieved_chunks.csv`: the same rows with the full retrieved text
- `retrieved_contexts.csv`: every retrieved chunk with rank, similarity, source paragraphs and text
- `configuration_summary.csv`: means for each of the nine configurations
- `answer_quality_llm_judge.csv`: every judge verdict (four 1 to 5 ratings, truncation flag, missed points, unsupported claims, comment), cached by content hash
- `judge_key_points.json`: the fixed checklist the judge uses for each question
- `scaling_results.csv`: 18 vs. 30 paragraphs
- `before_after_topk.csv`, `before_after_query_refinement.csv`, `before_after_answer_budget.csv`: the three fixes, before vs. after
- `failure_analysis_candidates.csv`: the weakest cases with full evidence
- `run_metadata.json`: models, device and settings
- `*_checkpoint.csv`: partial saves written after each embedding model, so an interrupted run can be inspected

## Reported run

Executed end to end on an Apple M4 Pro (24 GB, MPS, FP16). With the corpus as first written, a run on an RTX 5090 retrieved the same chunks as this machine in all 54 cases (45 of 54 answers word for word identical); latency differs by device. The reported run uses the corpus after three small wording edits, which moved 2 of the 54 retrievals.
