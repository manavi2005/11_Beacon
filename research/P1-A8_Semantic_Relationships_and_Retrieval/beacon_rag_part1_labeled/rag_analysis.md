## Part 1: Build the RAG Pipeline (90 pts)

### Step 1.1: Define Your Knowledge Base (10 pts)
The Beacon interview-coaching corpus is loaded from `data/beacon_knowledge_base.json`. The notebook validates paragraph counts and word lengths.

### Step 1.2: Text Representation & Chunking (25 pts)
Paragraphs are coherent source records with stable IDs. Fixed-length chunks pack whole sentences toward 180 words within sections; overlapping chunks use two paragraphs with a one-paragraph stride; hybrid chunks group complete paragraphs within sections up to 360 words. Source IDs are preserved.

### Step 1.3: Embedding Pipeline (15 pts)
BGE small/base/large v1.5 produce normalized 384/768/1024-dimensional embeddings, stored in a NumPy vector index with chunk metadata.

### Step 1.4: Retrieval System (20 pts)
The query is embedded using the matching BGE model, compared with stored vectors using cosine similarity, and the top-k chunks are returned with full text and source IDs.

### Step 1.5: Generation Pipeline (20 pts)
A fixed Qwen3-4B-Instruct-2507 model receives a system instruction, retrieved chunk context, and the user query. It generates a cited response. The same model and generation settings are used across all nine configurations.

---

# P1-A8 — Beacon RAG Analysis

**Project:** Beacon, an AI interview-preparation coach  
**Team:** Career Coaches  
**Generation model:** `Qwen/Qwen3-4B-Instruct-2507` (fixed across all experiments)  
**Embedding models:** BGE small/base/large v1.5 (384/768/1024 dimensions)

> **Experimental integrity note:** This report contains the system design, corpus definition, evaluation method, and analysis framework. Numeric retrieval, answer, and latency results must come from executing `rag_system.ipynb` on the team's machines. No experimental outcomes have been invented in this report. Fill the result tables and failure examples from the generated CSV files after the run.

## 1. Knowledge base and document representation

### 1.1 Knowledge-base scope

The knowledge base answers questions about Beacon's AI interview-coach product: candidate onboarding, role-specific skill blueprints, the shared skill catalog, skill diagnosis, readiness, preparation plans, task progress, STAR-based answer review, mock interviews, spaced repetition, coach chat, model safety, validation, provider configuration, and system architecture.

The source materials supplied for this assignment were:

- Beacon product `README.md`;
- Django `models.py` (including `Skill`, `CandidateProfile`, `SkillAssessment`, `PreparationPlan`, `PlanTask`, and `TaskAttempt`);
- A7 `system_design.md`;
- the team's A6/A7 `ai_prototype` model-selection notebook.

The corpus file `data/beacon_knowledge_base.json` contains **30 paragraphs and approximately 3,021 words**. Each paragraph is a complete, standalone explanation with a stable source ID, section ID, topic, and source label. The notebook validates that each paragraph is 80–200 words and that the corpus is within the assignment's 2,000–5,000-word target. The content is a curated paraphrase of the supplied project materials rather than a dump of candidate records. It contains no real user resumes or private profile data.

**Data-model note:** The uploaded `models.py` header describes five models, but the file contains six Django model classes when `TaskAttempt` is included. The corpus describes the `TaskAttempt` model because it documents how a task's passing evidence is recorded.

### 1.2 What counts as a paragraph

A paragraph is one complete explanatory unit in the knowledge base. It has one primary topic, a stable ID such as `B12`, and an explicit source label. Paragraphs were kept between 80 and 200 words. Related paragraphs are grouped under a section ID so chunking can preserve topic boundaries.

### 1.3 Chunking strategies

| Strategy | Implementation | Boundary / overlap behavior | Intended trade-off |
|---|---|---|---|
| Fixed length | Sentence-aware packing toward 180 words | Splits only between complete sentences; packing is scoped to a section so unrelated topics are not mixed | More granular retrieval, with a risk of splitting related explanation across chunks |
| Overlapping paragraphs | Two adjacent paragraphs per chunk, stride one | For paragraphs 1–3 in a section: (1+2), then (2+3); paragraph 2 is repeated | Preserves local context across chunk boundaries, at the cost of duplicated text and more chunks |
| Hybrid / strategic | Merge complete paragraphs by section up to a 360-word cap | Uses paragraph boundaries; oversized sections are split between paragraphs; no cross-section merging | Keeps a coherent topic together, with fewer but longer chunks |

Each resulting chunk stores its strategy, chunk ID, section, source paragraph IDs, text, and word count. This metadata is retained in the retrieved-context output so a reviewer can inspect the exact evidence that was passed to the generator.

## 2. Models and pipeline

### 2.1 Embedding models

The selected models are from the same BGE v1.5 English model family. Using one family helps reduce confounding caused by unrelated training objectives or architecture differences while still meeting the assignment's dimension tiers.

| Size | Hugging Face model | Dimensions | Model card |
|---|---|---:|---|
| Small | `BAAI/bge-small-en-v1.5` | 384 | [Hugging Face](https://huggingface.co/BAAI/bge-small-en-v1.5) |
| Medium | `BAAI/bge-base-en-v1.5` | 768 | [Hugging Face](https://huggingface.co/BAAI/bge-base-en-v1.5) |
| Large | `BAAI/bge-large-en-v1.5` | 1024 | [Hugging Face](https://huggingface.co/BAAI/bge-large-en-v1.5) |

The BGE model cards list MIT licensing and the corresponding dimensions. The notebook normalizes both passage and query embeddings and uses dot product as cosine similarity. For retrieval, it prefixes queries with `Represent this sentence for searching relevant passages:` and leaves passage text unprefixed.

### 2.2 Fixed generation model

The team's A6/A7 model-selection notebook includes `Qwen/Qwen3-4B-Instruct-2507` in its Large model category. That exact ID is used for every RAG experiment. The model is loaded through Hugging Face Transformers, not Ollama. It uses greedy decoding, one system prompt, and a fixed output-token limit. These controls keep generation settings constant while comparing embeddings and chunking.

Model card: [Qwen/Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507), Apache-2.0 license.

### 2.3 System pipeline

```mermaid
flowchart LR
    A[Beacon Knowledge Documents] --> B[Paragraph Validation]
    B --> C[Chunking Strategy]
    C --> D[Sentence Transformer Embeddings]
    D --> E[Normalized Vector Store]
    F[User Query] --> G[Query Embedding]
    G --> E
    E --> H[Top-k Retrieved Chunks]
    H --> I[Grounded Prompt]
    I --> J[Qwen3-4B-Instruct-2507]
    J --> K[Answer with Chunk Citations]
    K --> L[Evaluation and Logging]
```

## 3. Experiment setup and evaluation

### 3.1 Nine configurations

The notebook runs the following matrix:

| Embedding model | Fixed length | Overlapping paragraphs | Hybrid / strategic |
|---|---:|---:|---:|
| BGE small (384) | ✓ | ✓ | ✓ |
| BGE base (768) | ✓ | ✓ | ✓ |
| BGE large (1024) | ✓ | ✓ | ✓ |

Each configuration receives the same six test queries, top-k=3, the same knowledge base, the same generation model, the same prompt, and the same decoding settings. The main experiment therefore contains 54 query-level outputs (9 configurations × 6 queries).

### Step 2.1: Define Test Queries (10 pts)

1. How does Beacon turn a target role into a personalized skill blueprint and decide what a candidate should focus on next?
2. How is the readiness percentage calculated, and why can a strong skill not hide a weakness in another skill?
3. What information does Beacon store in a candidate profile, including the target role, resume, experience, and interview deadline?
4. How does Beacon evaluate a behavioral interview answer using STAR, especially when an answer is vague or has no result?
5. How does Beacon record preparation-task completion and connect a completed task to evidence of skill progress?
6. How does Beacon protect resume and interview text from prompt injection and validate the AI response before showing it?

Each query has a manually assigned set of relevant paragraph IDs and expected answer terms in the notebook. These labels are withheld from retrieval and generation; they are used only after retrieval to evaluate evidence coverage.

### 3.3 Evaluation metrics

| Metric | Calculation | Interpretation |
|---|---|---|
| Context recall | Gold paragraph IDs found in retrieved chunks ÷ all gold paragraph IDs | How much of the known relevant source material was retrieved |
| Context precision | Retrieved chunks containing at least one gold paragraph ÷ retrieved chunks | How much of the retrieved context was relevant |
| Context F1 | `2 × precision × recall ÷ (precision + recall)` | Harmonic mean balancing recall and precision |
| Noise rate | 1 − context precision | Share of retrieved chunks that did not match the gold labels |
| Answer keyword coverage (proxy) | Expected terms present in answer ÷ expected terms | Reproducible lexical proxy; not a full semantic quality score |
| Human answer quality | Four human ratings (1–5), combined with A7 weights into a 1–10 score | Manual semantic assessment using the prior model-selection rubric |
| Retrieval latency | Query embedding + similarity search time | Time spent finding evidence |
| Generation latency | Time inside model generation | Time spent producing the response |
| Total query latency | Retrieval latency + generation latency | End-to-end measured query time, excluding one-time model loading |

**How the prior notebooks score answers:** `ai_prototype(2).ipynb` evaluates its STAR-grading route using **format reliability** (share of replies in the requested valid JSON shape) and **judgement accuracy** (share placed on the correct side of the grading threshold). Its evaluation section also names instruction adherence, task accuracy, safety, speed, and footprint. It does not define a retrieval-quality calculation. `multi_model_system.ipynb` defines the weighted generation-quality score: accuracy (0.35), structure (0.25), instruction adherence (0.25), and clarity (0.15), with `score_1_to_10 = 1 + 9 × quality`.

**Human rating rubric for this RAG task:** rate each dimension from 1 to 5 and normalize it as `(rating − 1) ÷ 4`. Accuracy = whether factual claims are correct and supported by retrieved evidence; structure = whether every part of the question is answered in a clear order; instruction adherence = whether the answer stays within context, cites retrieved chunks accurately, and admits missing information; clarity = completeness, readability, concision, and absence of repetition/truncation. Apply the same A7 weights and 1–10 conversion formula. Fill the four rating columns in `outputs/answer_quality_review_template.csv`, then save the completed file as `outputs/answer_quality_reviews.csv`. The notebook reads those ratings and computes the composite score.

The keyword metric is deliberately labelled a proxy. It may penalize a valid paraphrase or reward a phrase that appears without being explained correctly. It should be read alongside retrieved chunks and human review, not as a replacement for semantic answer quality.

### Step 2.2: Evaluation Table (40 pts) — Populate after execution

The notebook writes `outputs/configuration_summary.csv` and renders dynamic Markdown answers after the model-testing cell. The numeric placeholders below remain blank until the notebook is run; the notebook does not fabricate model results. Copy the measured means into this report:

| Embedding model | Chunking strategy | Mean context recall | Mean context precision | Mean context F1 | Mean answer keyword coverage proxy | Mean human answer quality (1–10) | Mean total latency (s) |
|---|---|---:|---:|---:|---:|---:|
| BGE small (384) | Fixed | — | — | — | — | — | — |
| BGE small (384) | Overlap | — | — | — | — | — | — |
| BGE small (384) | Hybrid | — | — | — | — | — | — |
| BGE base (768) | Fixed | — | — | — | — | — | — |
| BGE base (768) | Overlap | — | — | — | — | — | — |
| BGE base (768) | Hybrid | — | — | — | — | — | — |
| BGE large (1024) | Fixed | — | — | — | — | — | — |
| BGE large (1024) | Overlap | — | — | — | — | — | — |
| BGE large (1024) | Hybrid | — | — | — | — | — | — |

The actual retrieved text is in `outputs/retrieved_contexts.csv`; `outputs/evaluation_results.csv` includes the generated answers and query-level measurements. These files satisfy the requirement to show retrieved chunks, not just final answers.

## 4. Analysis questions — complete from measured outputs

### Step 2.3: Compare Embedding Models (20 pts)

Use `configuration_summary.csv` and aggregate the metrics across chunking strategies. Discuss:

- Whether 384 → 768 → 1024 dimensions increased context recall or precision.
- Whether answer keyword coverage and blinded human ratings moved in the same direction as retrieval metrics.
- Whether a larger embedding model improved quality enough to justify greater embedding compute, storage, and latency.
- Whether any query behaved differently from the overall average.

**Finding:** [Insert the measured comparison. Do not assume the largest model wins.]

### Step 2.4: Compare Chunking Strategies (20 pts)

Compare the three strategies across the same embedding model and query. Discuss:

- Whether fixed chunks were more precise but occasionally missed neighboring explanation.
- Whether overlap increased evidence recall while duplicating content or increasing noise.
- Whether hybrid chunks preserved complete concepts but returned broader context.
- How retrieved-context differences affected the grounded answer and its citations.

**Finding:** [Insert the measured comparison and cite specific query IDs/chunk IDs.]

### Step 2.5: Data Scaling Experiment (10 pts)

The notebook compares the first 18 paragraphs (smaller subset) with the full 30-paragraph corpus. It uses three queries whose gold evidence is contained in both datasets. `outputs/scaling_results.csv` reports context recall, precision, noise, keyword coverage, and latency.

| Dataset | Paragraphs | Mean context recall | Mean context precision | Mean noise rate | Mean answer keyword coverage | Mean total latency (s) |
|---|---:|---:|---:|---:|---:|---:|
| Smaller subset | 18 | — | — | — | — | — |
| Full corpus | 30 | — | — | — | — | — |

**Finding:** [Explain whether adding paragraphs improved evidence coverage or introduced distractors. Separate the number of documents from their topical relevance.]

## Part 3: Failure Analysis & Improvement (60 pts)

### Step 3.1: Failure Cases (30 pts)

Use `outputs/failure_candidates.csv` as a starting point, then inspect the corresponding full chunk texts in `outputs/retrieved_contexts.csv`. If fewer than three rows cross the provisional thresholds, discuss the three weakest near misses instead and label them as near misses.

| Case | Embedding / chunking | Query ID | Retrieved chunk IDs | Observed failure | Likely root cause | Evidence |
|---|---|---|---|---|---|---|
| 1 | [fill] | [fill] | [fill] | [wrong / incomplete / unsupported answer] | [chunking / embedding / query / prompt / generation] | [refer to exact retrieved text and answer] |
| 2 | [fill] | [fill] | [fill] | [fill] | [fill] | [fill] |
| 3 | [fill] | [fill] | [fill] | [fill] | [fill] | [fill] |

### Step 3.2: Root Cause Analysis (15 pts)

Root-cause guide:

- **Chunking:** the required explanation was split across chunks, merged with a different idea, or too broad to rank clearly.
- **Embedding model:** semantically relevant language was not ranked highly even though the source passage existed and the query was clear.
- **Query formulation:** the question omitted a key term, used an ambiguous phrase, or asked multiple questions at once.
- **Prompt / generation:** relevant evidence was retrieved but the model ignored it, made an unsupported inference, or failed to cite its context.
- **Knowledge-base coverage:** the requested answer was not present in the supplied project materials. Do not call this a retrieval failure when the corpus itself lacks the fact.

### Step 3.3: System Improvement (15 pts)

The notebook implements one controlled change: increase top-k from 3 to 5 for query Q1, while keeping BGE-base, hybrid chunking, the generation model, and prompt unchanged. Use `outputs/before_after_topk.csv`.

| Setting | top-k | Context recall | Context precision | Noise rate | Answer keyword coverage | Total latency (s) |
|---|---:|---:|---:|---:|---:|---:|
| Before | 3 | — | — | — | — | — |
| After | 5 | — | — | — | — | — |

**Interpretation:** [State whether the change improved recall, whether precision/noise worsened, whether the answer improved, and whether extra context increased latency. If it did not improve the result, report that honestly and propose another fix.]

## Part 4: System Design Reflection (50 pts)

### Step 4.1: Cost Awareness (15 pts)

- **Embedding dimension:** for float32 vectors, one vector uses approximately `dimensions × 4 bytes`. That is 1,536 bytes at 384 dimensions, 3,072 bytes at 768 dimensions, and 4,096 bytes at 1,024 dimensions. At this assignment's corpus size, vector storage is small; at larger scale, dimension affects index memory, disk storage, and similarity-computation cost.
- **Chunk size:** smaller chunks create more vectors and index entries, increasing embedding work and index overhead. Larger chunks reduce the number of vectors but may retrieve irrelevant material and consume more LLM context tokens per result.
- **Top-k:** increasing k normally increases retrieved text, input tokens, prompt processing, and generation latency. It can improve evidence coverage but may add noise and distract the generator.
- **One-time versus per-query cost:** model download and loading are startup costs. Query embedding, vector search, and LLM generation recur per user query. The notebook reports model load separately from per-query latency.

### Step 4.2: RAG vs Alternatives (15 pts)

| Approach | When to use | Beacon example | Main trade-off |
|---|---|---|---|
| RAG | Answers need to be grounded in changing or inspectable project knowledge and source evidence should be shown | Explain how CandidateProfile, SkillAssessment, task progress, or Beacon features work | Adds retrieval/indexing complexity; quality depends on corpus, chunks, and embeddings |
| Fine-tuning | Desired behavior, style, or task format should be learned from many representative examples | Train a coach to consistently grade STAR answers using a curated dataset of reviewed examples | Requires quality training data and retraining; does not automatically provide up-to-date project facts |
| Pure prompting | Task is self-contained and required facts fit in the prompt | Ask the model to rewrite a supplied practice answer or produce a one-off explanation from a provided profile | No retrieval setup, but the model cannot reliably know private or changing project facts not included in the prompt |

RAG is appropriate for this assignment because the objective is to retrieve Beacon-specific knowledge and inspect how retrieval changes the generated answer. Fine-tuning and prompting solve different problems and are not mutually exclusive with RAG.

### Step 4.3: System Design (20 pts) — Scale to 10K users/day

The team's A7 system-design document estimated five AI jobs per active user per day for its earlier Beacon workload. At 10,000 daily active users, that was approximately 50,000 AI jobs/day and 16–19 million tokens/day under the A7 token assumptions. These are A7 planning estimates, not measurements of the new RAG feature; RAG context adds input tokens and must be measured separately.

A production design should:

1. **Separate web traffic from inference:** keep Django web workers stateless where possible and send RAG requests to an inference service behind a queue.
2. **Persist and version the index:** store embeddings and chunk metadata in a persistent vector store; re-embed only changed source paragraphs and keep a corpus/index version for reproducibility.
3. **Batch and cache embeddings:** batch ingestion and query embedding where latency allows; cache embeddings for identical normalized queries and unchanged documents.
4. **Control generation throughput:** use bounded queues, request timeouts, concurrency limits, and a GPU inference server with dynamic batching. Apply backpressure rather than allowing memory exhaustion.
5. **Protect candidate data:** keep candidate-specific data behind authentication and row-level authorization; separate shared Beacon product knowledge from private resumes, answers, and progress records.
6. **Measure quality and operations:** track recall/precision on a reviewed query set, citation support, p50/p95 latency, token use, queue depth, error rate, and model/index versions.
7. **Degrade safely:** if retrieval returns no relevant context, say that the knowledge base does not document the answer. If generation fails, use the existing transparent fallback pattern rather than fabricate an answer.

### Additional design priorities

For the prototype, optimize retrieval relevance and evidence visibility before tuning infrastructure. Once a chunking/embedding combination is selected, optimize index persistence, ingestion caching, query batching, and top-k. At production scale, generation throughput and concurrency will likely dominate compute cost, while vector storage remains relatively modest for a Beacon product knowledge base. Candidate-specific privacy controls are a design requirement, not an optional optimization.

## 7. Limitations

- The supplied Beacon corpus is documentation-derived and intentionally excludes real user data. It supports product and data-model questions, not personalized career advice for a real candidate.
- The fixed paragraph gold labels are manually curated for this assignment. They are useful for repeatable evaluation but do not represent every possible relevant chunk.
- Keyword coverage is a lexical proxy. Human ratings and source inspection are required for semantic answer quality.
- Local latency depends on GPU/CPU, OS, PyTorch build, thermals, memory pressure, and model cache state. Compare configurations on the same machine and report hardware with the results.
- The notebook uses an exact NumPy index because the corpus is small. A production 10K-user system needs a persistent, concurrency-safe index and an inference-serving layer.

## 8. References

- Beacon product README supplied by the team.
- Beacon `models.py` supplied by the team.
- Team A7 `system_design.md` and A6/A7 model-selection notebook supplied by the team.
- [BGE small v1.5 model card](https://huggingface.co/BAAI/bge-small-en-v1.5).
- [BGE base v1.5 model card](https://huggingface.co/BAAI/bge-base-en-v1.5).
- [BGE large v1.5 model card](https://huggingface.co/BAAI/bge-large-en-v1.5).
- [Qwen3-4B-Instruct-2507 model card](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507).
