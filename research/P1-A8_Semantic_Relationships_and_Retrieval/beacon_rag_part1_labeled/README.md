# Beacon RAG — P1-A8 Semantic Relationships and Retrieval

This submission builds a retrieval-augmented generation (RAG) assistant for **Beacon**, the team's AI interview-preparation coach. It retrieves documented Beacon product and data-model knowledge before asking a fixed language model to answer questions.

## Files

```text
beacon_rag_submission/
├── rag_system.ipynb
├── rag_analysis.md
├── requirements.txt
├── README.md
├── data/
│   └── beacon_knowledge_base.json
└── outputs/                 # created by the notebook
```

The JSON corpus is an additional required input to the notebook. It contains 30 complete paragraphs (about 3,000 words), each with an ID, section, topic, source label, and text. The knowledge base was prepared from the supplied Beacon `README.md`, `models.py`, and A6/A7 `system_design.md` / model-selection notebook. It describes product features and documented model/data behavior; it is not a user's private candidate profile or resume.

## Models used

### Embeddings (Hugging Face / Sentence Transformers)

| Assignment size | Model ID | Dimensions |
|---|---|---:|
| Small | `BAAI/bge-small-en-v1.5` | 384 |
| Medium | `BAAI/bge-base-en-v1.5` | 768 |
| Large | `BAAI/bge-large-en-v1.5` | 1024 |

These are three sizes from the same BGE v1.5 family. Their model cards are available at [BGE small](https://huggingface.co/BAAI/bge-small-en-v1.5), [BGE base](https://huggingface.co/BAAI/bge-base-en-v1.5), and [BGE large](https://huggingface.co/BAAI/bge-large-en-v1.5). The BGE cards identify the 384/768/1024 dimensional variants and list MIT licensing.

### Generation

The fixed generation model is **`Qwen/Qwen3-4B-Instruct-2507`**. This exact Hugging Face model ID appears in the team's supplied A6/A7 model-selection notebook. It is kept unchanged across the nine RAG configurations. The Hugging Face model card lists the Apache-2.0 license and gives a Transformers loading example: [Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507).

Generation is performed directly with `transformers`; Ollama is not required. This also makes the notebook's model identity explicit and repeatable.

## Why `ollama list` failed in PowerShell

The error `ollama : The term 'ollama' is not recognized ...` means PowerShell cannot locate an `ollama.exe` command. Common causes are that Ollama is not installed on that Windows machine, or it is installed but its directory is not on the current `PATH` (or the terminal was not reopened after installation).

This RAG notebook does **not** call Ollama. It downloads and loads the fixed Qwen model from Hugging Face through `transformers`. You can verify that Ollama is discoverable with:

```powershell
Get-Command ollama -ErrorAction SilentlyContinue
where.exe ollama
```

Those commands are only relevant if you separately choose to run the Beacon Django application's optional Ollama-compatible API endpoint. They are not part of this assignment's notebook path.

## Environment setup

Python 3.11 is recommended. Create a separate environment, or use an existing Python 3.11 environment:

```powershell
conda create -n beacon-rag python=3.11 -y
conda activate beacon-rag
```

### 1. Install PyTorch for your hardware

Install a PyTorch build appropriate to the machine **before** installing the remaining requirements. On your Windows desktop, choose a CUDA-enabled PyTorch wheel compatible with the installed NVIDIA driver and RTX 5090. Use the current command from the official [PyTorch installation selector](https://pytorch.org/get-started/locally/); do not install a CPU-only wheel by mistake.

On an Apple Silicon Mac, install the standard PyTorch wheel, which provides the MPS backend when supported by the OS and hardware.

### 2. Install project dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Verify hardware detection

```powershell
python -c "import torch; print('CUDA:', torch.cuda.is_available()); print('MPS:', hasattr(torch.backends, 'mps') and torch.backends.mps.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'not using CUDA')"
```

Expected behavior: the RTX 5090 desktop should report CUDA as available; an Apple Silicon Mac should report MPS as available. If both are false, the notebook falls back to CPU, but running the 4B generation model in FP32 can use a substantial share of a 24 GB system's memory. GPU/MPS execution is recommended for this submission.

### 4. Start Jupyter

From the `beacon_rag_submission` directory (the directory containing this README):

```powershell
jupyter lab
```

Open `rag_system.ipynb` and run all cells from top to bottom. The first run downloads the three embedding models and the Qwen3 generation model from Hugging Face; subsequent runs use the local Hugging Face cache.

## Hardware and memory strategy

The team's machines are different: a Windows desktop with a Ryzen 9 9800X3D and RTX 5090 (32 GB VRAM), and a MacBook with 24 GB unified memory. The notebook is deliberately conservative:

- it keeps the same 4B Qwen generator loaded once;
- it loads only one embedding model at a time and releases it before loading the next;
- it uses an embedding batch size of 16;
- it uses FP16 for CUDA/MPS generation and limits generation to 220 new tokens;
- it uses an in-memory NumPy exact-cosine index for this small corpus rather than running a separate vector database service;
- it does not load all three embedding models simultaneously.

The RTX 5090 has ample VRAM for this experiment. On the 24 GB Mac, close memory-intensive applications before running the full notebook. The Qwen model's FP16 weights are roughly 8 GB; actual peak memory also includes PyTorch, model activations, the embedding model, the OS, and other applications. The notebook does not deliberately allocate a 24 GB working set, but peak usage depends on the local software environment.

## What the notebook runs

1. Validates 30 paragraphs, paragraph word counts, and total corpus size.
2. Builds fixed-length, overlapping-paragraph, and hybrid/strategic chunks.
3. Embeds each chunk with all three BGE models and indexes the normalized vectors.
4. Retrieves top-k context for six fixed Beacon questions.
5. Generates each answer with the same Qwen3-4B-Instruct-2507 model and fixed decoding settings.
6. Records retrieved chunk text, context recall/precision, a keyword-coverage proxy for answer quality, retrieval/generation latency, and token counts.
7. Compares an 18-paragraph subset with the complete 30-paragraph corpus.
8. Runs a before/after top-k experiment (k=3 versus k=5) for one fixed query.
9. Surfaces candidate failure cases for inspection.

## Output files

The notebook creates these files under `outputs/`:

- `evaluation_results.csv` — one row per embedding/chunking/query run, including the generated answer and measured latency;
- `retrieved_contexts.csv` — each retrieved chunk, rank, similarity, source paragraph IDs, and full text;
- `configuration_summary.csv` — mean metrics by each of the nine configurations;
- `scaling_results.csv` — smaller versus larger corpus experiment;
- `before_after_topk.csv` — top-k improvement comparison;
- `failure_candidates.csv` — low-scoring cases or near misses to review;
- `run_metadata.json` — model IDs, device, and run settings.

The notebook reports `answer_keyword_coverage_proxy`, not a definitive semantic score. Review generated answers and retrieved chunks, then add blinded human answer-quality ratings from 1 to 5 as described in `rag_analysis.md`. Do not describe a failure or improvement unless the saved outputs support it.

## Reproducibility notes

- The main experiment uses six fixed queries, top-k=3, greedy decoding (`do_sample=False`), a fixed prompt, and one generation model.
- Run the notebook from the project root so relative paths to `data/` and `outputs/` work.
- No API key, Ollama server, or private Beacon production database is required.
- Model downloads require Hugging Face network access on the first run. No model weights are copied into this submission ZIP.
- This is a local, in-memory vector-search prototype; the `rag_analysis.md` design section explains what should change for a production system serving 10,000 users per day.


## Part 2 and Part 3 evaluation workflow

After the nine-configuration experiment runs, the notebook renders assignment-labeled Markdown conclusions from the measured outputs and saves the full retrieved passages in `outputs/retrieved_contexts.csv` and `outputs/evaluation_table_with_retrieved_chunks.csv`.

Retrieval quality is evaluated with gold-label context recall, context precision, their harmonic mean (context F1), and noise rate. The two supplied A6/A7 evaluation notebooks do not define a retrieval metric. For answer quality, the notebook carries forward the A7 weighted score (accuracy 0.35, structure 0.25, instruction adherence 0.25, clarity 0.15; `1 + 9 × quality`) with RAG-specific human-rating criteria.

The notebook creates `outputs/answer_quality_review_template.csv`. Inspect each answer beside its retrieved chunks, fill the four human rating columns (1–5), and save the completed file as `outputs/answer_quality_reviews.csv`. Re-run the evaluation-summary cell to calculate the A6/A7-style 1–10 answer-quality score. The expected-term coverage value is only an automatic lexical proxy and must not be reported as semantic correctness.

The failure-analysis cell exports `outputs/failure_analysis_candidates.csv` with the actual retrieved text, generated answer, and provisional metric-based root-cause hypotheses. Confirm each root cause by inspecting the evidence; do not label a near miss as a proven hallucination.
