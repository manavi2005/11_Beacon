# Multi-Model System Design

**P1-A7 (Part 1 assignment): Model Size Selection and Benchmarking, Cost
Comparison and Infrastructure Planning, and Multi-Model Routing Strategy**
Team 11, Beacon. An interview-preparation coach that scores a candidate's
skills against a target role and grades their written practice answers.

The experiments, benchmarking and scaling simulations live in
[`multi_model_system.ipynb`](multi_model_system.ipynb) beside this file. This
document carries the reasoning: why the system is shaped the way it is, what
it costs, and how a request is routed to a model.

This part of the assignment is independent of the Django project. Where it
refers to Beacon, that is to keep the task realistic, because a model is only
fast enough or accurate enough relative to a job it has to do.

---

## 1. Model inventory and size categories

### The task the models are being judged on

Beacon asks a model for three things, and they are not equally hard:

| Job | What the model must produce | Why size might matter |
|---|---|---|
| **Screen** a written practice answer | Three fields: on topic, substantive, a provisional score | Classification. Cheap, and runs on every submission |
| **Grade** that answer | A score plus structured feedback: summary, strengths, fixes | Judgement. A lenient grader is worse than no grader |
| **Advise** on a weekly plan | A focus skill, three actions, a practice question | Reasoning over the candidate's whole profile |

Every one of them has to come back as valid JSON in a fixed shape, because an
unparsable reply is a broken feature rather than a worse answer. That makes
instruction adherence the first criterion, ahead of how good the content is.

### The 15 models

The same 15 models benchmarked in Assignment 6, unchanged. They were selected
there under four rules, all four of which still apply:

| Rule | Why it matters here |
|---|---|
| Loads with `transformers` (`AutoModelForCausalLM`) | The integration path is a local model held in the application process |
| Instruction or chat tuned, with a chat template | Beacon sends instructions and needs structured replies, not text continuation |
| Ungated, with no license click-through or token | Every teammate and the grader can reproduce the benchmark as-is |
| Runs on the development machine | An Apple M4 Pro with 24 GB of unified memory, with normal applications open |

### The categories

| Model category | Parameter range | Models | Weights in bf16 |
|---|---|---|---|
| **Ultra-Light** | < 0.5B | SmolLM2-135M, SmolLM2-360M, Qwen2.5-0.5B | 0.3 - 1.0 GB |
| **Light** | 0.5B - 1.2B | LFM2-700M, TinyLlama-1.1B, LFM2-1.2B | 1.5 - 2.3 GB |
| **Small** | 1.2B - 2B | OLMo-2-1B, Qwen2.5-1.5B, SmolLM2-1.7B | 3.0 - 3.4 GB |
| **Medium** | 2B - 3.5B | Granite-3.1-2B, Qwen2.5-3B, Falcon3-3B | 5.1 - 6.5 GB |
| **Large** | 3.5B - 4.5B | Phi-3.5-mini, Phi-4-mini, Qwen3-4B | 7.6 - 8.0 GB |

Three models per category, fifteen in total, bands contiguous and
non-overlapping. The notebook asserts all four of those rather than leaving
them to be read off the table.

### Why these boundaries and not the ones in the brief

The brief gives an example structure of `< 1B`, `1B-3B`, `3B-7B`, `7B-30B`,
`30B+`. Our models do not spread across those bands, and that is a result from
A6 rather than an omission.

A6 downloaded and tried a 7-8B tier: Qwen2.5-7B, Falcon3-7B and
Granite-3.1-8B. In bf16 each needs roughly 15-16 GB for weights alone. On a
24 GB machine that is also running a browser and an IDE, the system swapped
more than 20 GB to disk, generation slowed to a crawl, and the run hit its
time limit before finishing a single tier.

That is a finding worth stating plainly, because it shapes everything
downstream: **a 7B model is not a laptop-and-browser model.** It needs a
dedicated machine with 32 GB or more, or a GPU server, or it has to be reached
as a hosted API rather than held locally. The population of models we can hold
in process therefore tops out near 4B.

Three requirements are in tension, and only two of them can hold at once:

1. the same 15 models from A6
2. three models per category
3. the brief's example parameter ranges

Mapping our 15 onto the example ranges gives **4 / 6 / 5 / 0 / 0**, computed
in the notebook rather than asserted here. That breaks requirement 2 and
leaves two categories with nothing in them to benchmark. Since the brief
labels that structure an *Example structure* while stating the other two as
requirements, the ranges are the part that bends. We keep the same 15 models
and three per category, and divide the 0.1B to 4B range into five contiguous
bands.

### The bands are not arbitrary

They were drawn where the A6 matrix showed behaviour actually changing, not at
round numbers:

| Boundary | What changes across it |
|---|---|
| Ultra-Light to Light | Nothing yet. Both tiers are unreliable at returning valid JSON, 40% and 67% |
| Light to Small | Reliability arrives. All three Small models returned valid JSON on every task |
| Small to Medium | Judgement, not format. Both emit valid JSON; the Medium tier stops passing weak answers |
| Medium to Large | Diminishing returns. Quality 0.92 to 0.99, latency up about 50%, memory about 2.6 times the Small tier |

Each band also mixes vendors, so a comparison between tiers is a comparison of
sizes rather than of one family scaled up. Hugging Face, Alibaba Qwen,
Liquid AI, TinyLlama, AllenAI, IBM, TII and Microsoft are all represented, and
no category draws all three of its models from one vendor.

### What this implies before any benchmarking

Two expectations worth writing down now, so the later steps can confirm or
contradict them rather than quietly agreeing with whatever we find:

The useful range for Beacon is likely **Small and above**, because anything
below it cannot be trusted to return parsable JSON, and a reply the
application cannot read is not a cheaper answer but a missing one.

The interesting trade is likely **Small against Large**, not Ultra-Light
against Large. Both ends of that comparison work; what separates them is
judgement quality against roughly 2.5 times the memory and 50% more latency.
That is the decision a routing design has to make, and Steps 1.2 onward are
what should settle it.

---

## 2. Prompt types

Five prompt types, one per job Beacon asks a model to do. They match the five
categories in the brief, which is less of a coincidence than it looks: that
list is a fair decomposition of what any text-AI product asks for, and Beacon
asks for all five.

| # | Prompt type | Beacon's use | Output | Inputs |
|---|---|---|---|---|
| 1 | Classification | Screen an answer before grading it | `on_topic`, `substantive`, `score` | 5 |
| 2 | Structured extraction | Pull skill evidence out of a resume | `skills[]`, from a closed catalog | 5 |
| 3 | Summarization | One line stored with a practice attempt | `summary` | 5 |
| 4 | Text generation | The week's plan | `focus_skill`, `actions[3]`, `practice_question` | 5 |
| 5 | Prediction | Readiness forecast and bottleneck | `readiness_percent`, `bottleneck_skill` | 5 |

Twenty-five prompts in total, written out in section 3, which against fifteen
models gives a 375-cell benchmark matrix.

### Ordered by width of judgement

The order is deliberate. Classification asks for two booleans about a short
piece of text. Prediction asks the model to read a whole profile, apply an
unstated definition of readiness, commit to a number and name a bottleneck.

If parameter count buys anything, it should buy more at the bottom of that
list than the top, and the gap between tiers should widen as the task widens.
A benchmark built on one prompt type could not see that effect at all. This is
the main thing Step 1.2 exists to make measurable.

### Ordered by cost of failure

The five also differ in what a wrong answer costs, which is the number a
routing design actually trades against latency and memory:

| Prompt type | What a wrong answer does | Recoverable |
|---|---|---|
| Classification | Sends a weak answer to the grader, or blocks a good one | Yes, the second stage catches most of it |
| Structured extraction | Pre-fills onboarding with skills the candidate never claimed | Yes, but the user has to undo it |
| Summarization | Misdescribes an attempt in the candidate's own history | No, and nobody is likely to notice |
| Text generation | Sends someone to practise the wrong skill for a week | No, and it costs the user a week |
| Prediction | Tells someone they are ready when they are not | No |

That table is why the routing design later cannot be "use the cheapest model
that returns valid JSON". Valid JSON is the floor, not the bar. Classification
can tolerate a weaker model because a second stage follows it. Generation and
prediction cannot, because nothing downstream checks them.

### One prompt contract, so the benchmark measures models

Every prompt uses the same six-part layout carried over from A6: Role, Task,
Constraints, Output format, Safety boundary, Length. Varying the prompt style
between types would confound prompt design with model capability, and the
comparison here is between models.

User text always sits inside `<data>...</data>` in a user turn, never in the
system prompt, so an instruction hidden in a resume is quoted to the model
rather than issued to it. One extraction input carries a live injection
payload for exactly this reason, and the notebook asserts that no fixture
leaks into any system prompt.

### Scored, not read

Each prompt type ships with its scorer, so a type cannot be benchmarked
without someone having decided in advance what a good answer looks like.
Scores run 0 to 1 and all of them give partial credit, because models land in
the middle rather than at the ends:

| Prompt type | How the score is built |
|---|---|
| Classification | Two thirds for agreeing with the labelled verdict, one third for a usable score in range |
| Structured extraction | Half for staying inside the catalog, half for F1 against a gold set |
| Summarization | Half for respecting the word cap, half for carrying the required facts across |
| Text generation | Half for the right focus skill, 0.3 for three distinct usable actions, 0.2 for a real question |
| Prediction | 0.6 decaying with distance from the computed readiness, 0.4 for naming the right bottleneck |

The notebook validates the scorers before any model runs, which matters more
than it sounds. A scorer that cannot separate a good reply from a bad one
would make every tier look identical, and that failure would be invisible in
the results. Each one is run against a correct reply, a wrong reply and a
half-right reply, and has to rank all three in order.

### Readiness is computed, not judged

The prediction target is not a matter of opinion. It comes from a fixed
formula: how far each skill has come toward what the role requires,
capped at one per skill so a strength cannot mask a gap, then averaged. That
gives 76, 93, 59, 70 and 79 percent for the five profiles. A model is scored on
distance from that number, with full marks inside ten points and a
straight-line decay to zero at thirty. Without a computed target, "predict
readiness" would have no right answer and the type would measure nothing.

---

## 3. Evaluation prompts

Five prompts per type, twenty-five in total, each shaped like an input Beacon
would really receive.

### Twenty-five prompts from fifteen fixtures

| Fixture corpus | Count | Read by |
|---|---|---|
| Written practice answers | 5 | Classification, Summarization |
| Resumes | 5 | Structured extraction |
| Candidate profiles | 5 | Text generation, Prediction |

The reuse is deliberate. In the application one submitted answer is both
screened and summarised, and one profile drives both the weekly plan and the
readiness figure. Giving those pairs separate inputs would have made the
benchmark less like the product rather than more. The twenty-five rendered
prompts are still twenty-five distinct strings, because the instruction, the
schema and the task differ per type, and the notebook asserts that none of
them collide.

### What the inputs cover

Each corpus carries an easy case, a hard case, a degenerate case and an
adversarial one. A benchmark made only of clean inputs measures the wrong
thing: every model looks competent on a tidy resume.

| Corpus | The five inputs |
|---|---|
| Answers | Full STAR with a measurable result; a vague non-answer; something off topic; one with a real situation and action that stops before saying what changed; one carrying an injection payload |
| Resumes | Clean, matching four catalog skills; a barista job matching none; one with an injection payload; one spanning finance and data; one dense with jargon the catalog does not contain |
| Profiles | Four weeks out and well behind; six weeks out and nearly ready; ten weeks out and early; a career switcher with one enormous gap; one whose free-text note carries an injection payload |

Three of those are worth singling out because of what they catch.

**The answer with no result.** It has a genuine situation, a genuine action,
and enough length to look substantial. A model that scores on word count will
call it strong. Only a model actually reading for a result will mark it down.

**The barista resume.** The correct answer is an empty list. Models that want
to be helpful invent something instead, and A6 found exactly that behaviour in
the smaller tiers. The F1 scorer treats both-empty as a perfect match so that
returning nothing is properly rewarded here rather than scored as a miss.

**The jargon-dense resume.** PgBouncer, Redis, Terraform and p99 are all real
skills and none of them is in the catalog. This is where models stop obeying a
closed list, which is why instruction adherence is scored separately from
structure.

### Two properties the notebook enforces

**The widest-gap skill is different in all five profiles**, resolving to SQL,
version control, algorithms, financial markets and system design. An earlier
draft had two profiles whose biggest gap was SQL, which meant a model that
answered "SQL" every time would have scored on generation and prediction
without reading the input at all.

**Injection payloads reach all five prompt types.** An earlier draft had a
single payload sitting in a resume, so adversarial behaviour was only ever
measured on extraction. Payloads now also sit in a practice answer and in a
profile's free-text note, so classification, summarization, generation and
prediction are each tested through the field that type actually reads. The
notebook asserts that every payload lands inside the `<data>` fence and that
none has leaked into a system prompt.

---

## 4. Evaluation metrics

Defined before any model runs, so the metrics cannot be picked after seeing
which ones make a preferred model look good.

### The four scored metrics

| Metric | Question | Measured by |
|---|---|---|
| **Structure** | Did the output follow the expected format? | One JSON object, every required field present, right type, in range |
| **Instruction adherence** | Did the model follow instructions? | Bare JSON with no prose or fences, no invented keys, word caps respected, closed lists obeyed |
| **Accuracy** | Was the answer correct? | The per-type scorers from section 2, each against a known answer |
| **Clarity** | Was the output understandable? | Free-text fields complete, not truncated, not repetitive, not echoing the prompt |

Structure and adherence look like one metric and are not. Structure is the
shape. Adherence is everything else the prompt asked for. A6 found models that
returned flawless JSON containing skill names that were never in the supplied
list, and a single combined metric would have scored that as a near miss
rather than as the specific failure it is.

The worked example in the notebook makes the split concrete: a reply of
`{"skills": ["SQL", "Data Analytics", "Python fundamentals"]}` scores
structure 1.00, adherence 0.75, accuracy 0.37, clarity 1.00. One number would
have said 7.4 out of 10 and left the reader to guess why.

### Two metrics measured but kept out of the score

**Injection resistance.** Section 3 puts a payload into one input of every
prompt type, so this is measured across all five. It still stays out of the
weighted score, and the reason is not sample size: following an injected
instruction is a disqualifier, not a gradient. A model that scores 9 out of 10
everywhere and obeys the payload is not a nine, it is unusable, and averaging
the failure in would let strong numbers elsewhere buy it back. It is reported
as a gate. The notebook checks three outcomes, including the quiet failure
where a model never says the magic word but returns an empty answer because
the payload derailed the task.

**Latency.** A cost, not a quality. Folding seconds into a quality score fixes
an exchange rate between speed and correctness before we know what either is
worth, which is the question the routing design exists to answer. It stays a
separate axis.

### The 1 to 10 score

```
quality = 0.35 * accuracy
        + 0.25 * structure
        + 0.25 * instruction_adherence
        + 0.15 * clarity

score   = 1 + 9 * quality
```

`1 + 9 * quality` rather than `10 * quality`, because the brief asks for a
1 to 10 scale. A model that returns nothing usable scores 1, and the floor of
the scale means what it says.

The weights come from the cost-of-failure table in section 2, not from an
even split. Accuracy is heaviest because a well-formed wrong answer is the
most expensive thing Beacon can produce: nothing downstream catches it, and a
week spent practising the wrong skill is a real cost to a real person.
Structure and adherence sit at 0.25 each because an unparsable reply is a
broken feature rather than a worse answer. Clarity is lightest at 0.15
because it is the only one of the four measured by proxy.

### Why a computed rubric rather than a judgement

Two alternatives were considered and rejected.

Reading 375 outputs and rating them by hand would not be reproducible, and
whoever did the rating would know which model produced each reply.

Asking a larger model to judge would import that model's biases into a
benchmark whose whole purpose is comparing models, and would make the result
depend on a model that is not itself under test.

Every metric here is a function of the reply text and a known expected answer.
The same inputs give the same scores on any machine, and the rubric can be
read and argued with before the first model runs.

**Clarity is the honest exception**, and is labelled as a proxy wherever it
appears. Completeness, truncation, repetition and prompt echo travel with
being understandable without being the same thing. That is why it carries the
lowest weight.

### Validating the rubric before trusting it

A rubric that cannot tell a good reply from a bad one would make every tier
look identical, and that failure would be invisible in the results. So the
notebook grades twenty hand-written replies, four quality levels across all
five prompt types, and asserts the ranking holds:

| Reply quality | Mean score |
|---|---|
| Ideal | 10.0 |
| Good | 9.5 |
| Sloppy | 6.5 |
| Broken | 1.0 |

Checked per prompt type as well as on the mean. The per-type assertion is
non-increasing rather than strictly decreasing, for a reason worth recording:
an ideal reply and a merely good one can legitimately tie when the good one
gets the answer right and breaks no stated constraint. An earlier draft
asserted a strict ordering and printed a claim the data did not support, which
is the kind of thing a validation step exists to catch.

---

## 5. Benchmark results

375 generations: 15 models against all 25 prompts, greedy decoding, run locally
through `transformers` on an M4 Pro with 24 GB. Every model loaded; nothing
failed. Raw replies are kept in `benchmark_results.csv` so any score here can
be audited, and the table in the shape the brief asks for is in
`benchmark_table.csv`.

### By category

| Category | Score (1-10) | Parsed | Latency | Tokens/sec |
|---|---|---|---|---|
| Large | 9.52 | 100% | 3.11s | 10.8 |
| Medium | 9.31 | 99% | 2.10s | 14.8 |
| Small | 7.79 | 84% | 1.10s | 27.7 |
| Light | 5.90 | 61% | 1.15s | 44.6 |
| Ultra-Light | 4.83 | 55% | 0.77s | 64.6 |

The ordering by category is clean and monotonic. That turns out to say much
less than it appears to, for reasons in section 6.

### By prompt type

| Category | Classification | Extraction | Summarization | Generation | Prediction |
|---|---|---|---|---|---|
| Ultra-Light | 3.50 | 6.48 | 3.40 | 5.56 | 5.23 |
| Light | 6.28 | 6.15 | 3.37 | 7.65 | 6.06 |
| Small | 9.36 | 9.27 | 2.77 | 9.16 | 8.41 |
| Medium | 9.64 | 9.47 | 8.95 | 9.68 | 8.81 |
| Large | 9.57 | 9.58 | 9.77 | 9.68 | 9.00 |

**Summarization is the outlier, and it is the most interesting column in the
benchmark.** Every other prompt type improves roughly monotonically with size.
Summarization collapses below Medium and does not recover: the Small tier
scores 2.77, which is lower than the Ultra-Light tier managed.

The cause is visible in the raw replies. **54 of the 375 replies contained no
JSON at all, and 33 of those are summarization.** Models below Medium did not
produce malformed JSON for this task; they produced no JSON, answering in
plain prose instead. OLMo-2-1B returned "The candidate's own history page
states that they owned the data cleaning..." as a bare sentence.

That is worth naming precisely: a free-text task pulls a model toward prose
strongly enough to override an explicit output-format instruction, and smaller
models give in to that pull. It is not a reading-comprehension failure. Those
prose summaries are mostly decent summaries. They are simply not parsable, and
Beacon cannot store an answer it cannot parse.

The Small-versus-Ultra-Light inversion in that column is one cell different out
of fifteen and should not be read as meaningful. Both tiers fail; the ordering
between two failures is noise.

### The four metrics behind the score

| Category | Structure | Adherence | Accuracy | Clarity |
|---|---|---|---|---|
| Ultra-Light | 0.480 | 0.483 | 0.322 | 0.483 |
| Light | 0.613 | 0.563 | 0.453 | 0.613 |
| Small | 0.840 | 0.833 | 0.603 | 0.840 |
| Medium | 0.987 | 0.977 | 0.814 | 0.987 |
| Large | 1.000 | 1.000 | 0.849 | 0.997 |

Structure and adherence saturate at Medium: both reach 1.000 at Large and
0.98 at Medium. **Accuracy does not.** It reaches only 0.849 at the top, and
the gap between Medium and Large on accuracy is 0.035.

This is the practical finding from the metric split. Past about 2B, extra
parameters are buying almost nothing in format compliance, because format
compliance is already solved. What is left unsolved is being right, and that
is the axis where the Large tier barely improves on the Medium tier.

### Data quality

Checked before drawing conclusions, because a reply cut off by the token
budget scores zero on structure and looks identical to a model that cannot
produce JSON at all.

9 of 375 replies (2.4%) opened a JSON object and never closed it:

- **5** are a model echoing the `<data>` block back instead of answering. No
  token budget fixes that; A6 recorded the same behaviour in the same tier.
- **2** had already written about 50 words against a 25-word cap, so the
  truncation marks a model that had broken the stated constraint first.
- **1** is a genuine harness artifact: SmolLM2-360M was writing correct
  pretty-printed JSON on a prediction prompt and ran out of budget before the
  closing brace. Pretty-printing costs tokens a compact reply does not.

One cell in 375 where our budget, rather than the model, set the score. That
is small enough to leave in and large enough to state.

---

## 6. Analysis

### 6.1 Which model category produced the best outputs?

**Large, at 9.52 out of 10.** But the honest version of that answer has three
qualifications, and they matter more than the headline.

**The gap to Medium is 0.21 points.** Medium scores 9.31 at two thirds of the
latency and roughly two thirds of the memory.

**The best single model is not in Large.** Qwen2.5-3B-Instruct, in Medium,
scores 9.62, ahead of all three Large models (9.60, 9.50, 9.46). The category
with the best average does not contain the best model.

**Large does not win every prompt type.** Medium takes classification (9.64)
and text generation (9.68). Large takes extraction, summarization and
prediction. Prediction is where the Large tier's advantage is clearest at 9.00
against 8.81, and prediction is also the weakest prompt type for both of the top tiers,
which fits: the widest-judgement task is the one where capacity still helps.

So the defensible claim is narrower than "Large is best". **Capability
saturates at Medium for four of the five prompt types**, and the remaining
advantage of the Large tier is concentrated in the hardest one.

### 6.2 Did larger models always perform better?

**No, and not by a small margin.**

**17 of the 105 model pairs are inverted**, meaning the smaller model scored
higher. **6 of the 15 models beat at least one model larger than themselves.**

The single clearest case: **TinyLlama-1.1B scores 2.65, while
Qwen2.5-0.5B scores 8.63.** The larger model is 2.2 times the size and scores
3.3 times worse.

Rank correlation between parameter count and score tells the same story in one
number, once it is split:

| Population | Rank correlation |
|---|---|
| All 15 models | 0.83 |
| Below 2B (9 models) | 0.47 |
| 2B and above (6 models) | 0.14 |

The strong overall correlation is an artifact of pooling. Within either half of
the range, size barely predicts quality at all. It looks strong overall only
because the bottom of the range contains models that fail outright and the top
contains models that work.

The sharpest illustration is a single narrow band. **Five models sit between
1.0B and 1.8B, a 1.55x size range, and they span 6.00 points of score:**

| Model | Parameters | Score |
|---|---|---|
| TinyLlama-1.1B-Chat | 1.10B | 2.65 |
| LFM2-1.2B | 1.17B | 6.13 |
| OLMo-2-1B-Instruct | 1.48B | 7.28 |
| Qwen2.5-1.5B-Instruct | 1.54B | 7.46 |
| SmolLM2-1.7B-Instruct | 1.71B | 8.65 |

Six points of range from 1.6x of size. Whatever is driving that is not
parameter count. TinyLlama is the oldest checkpoint in the set and the worst
by a distance; the newer small models from Qwen, Liquid AI and Hugging Face
are dramatically better at the same size. **Below about 2B, vintage and
training recipe dominate size.**

### 6.3 Which model gave the best balance between speed and quality?

Answered with a Pareto frontier rather than a blended score. Blending seconds
and quality requires an exchange rate between them, and choosing one would
decide the answer rather than find it.

Four models are Pareto optimal, meaning nothing else is both faster and better:

| Model | Category | Params | Score | Latency |
|---|---|---|---|---|
| SmolLM2-360M-Instruct | Ultra-Light | 0.36B | 3.72 | 0.61s |
| Qwen2.5-0.5B-Instruct | Ultra-Light | 0.49B | 8.63 | 0.64s |
| LFM2-700M | Light | 0.74B | 8.92 | 0.76s |
| Qwen2.5-3B-Instruct | Medium | 3.09B | 9.62 | 1.97s |

SmolLM2-360M is on the frontier only because it is fast; at 3.72 it is not a
candidate for anything. The real choice is among the other three.

**On quality against latency alone, the answer is Qwen2.5-0.5B-Instruct.** It
delivers 90% of the best score for 3.1x less latency and 6.3x fewer
parameters. LFM2-700M is slightly better and slightly slower, and the two are
close enough to be interchangeable on these numbers.

**Then the injection gate changes the answer.** It is scored as pass or fail
rather than averaged in, for the reason given in section 4: obeying an
injected instruction is a disqualifier, not a gradient. Only **5 of the 15
models** resist on all five adversarial prompts:

| Model | Params | Score | Latency | Gate |
|---|---|---|---|---|
| Qwen2.5-0.5B-Instruct | 0.49B | 8.63 | 0.64s | pass |
| granite-3.1-2b-instruct | 2.53B | 9.23 | 2.02s | pass |
| Falcon3-3B-Instruct | 3.23B | 9.08 | 2.31s | pass |
| Phi-3.5-mini-instruct | 3.82B | 9.60 | 3.12s | pass |
| Phi-4-mini-instruct | 3.84B | 9.46 | 3.32s | pass |

**Both of the other two frontier models fail it.** LFM2-700M resists 4 of 5,
and so does Qwen2.5-3B-Instruct, the highest-scoring model in the whole
benchmark. Size does not predict this either: a 0.49B model passes where a 4B
model does not.

**The answer to the question as asked is Qwen2.5-0.5B-Instruct.** It is on the
Pareto frontier, it is the fastest model that scores above 8, and it is the
only model below 2.5B that passes the safety gate. For a screening stage that
runs on every submission, 0.64 seconds at 8.63 with clean injection resistance
is a better buy than 1.97 seconds at 9.62 from a model that can be talked out
of its instructions.

If one model had to serve every prompt type, it would be
**Phi-3.5-mini-instruct**: 9.60, the highest score among the gate-passing
models, at 3.12 seconds. That is the cost of not routing, and it is the
argument for routing.

### What this implies for the system design

Three things carry into the routing design:

**There is no single best model, and the benchmark says so in three separate
ways.** The best average category does not contain the best model, the best
model fails the safety gate, and the best quality-per-second model is 6x
smaller than the best quality model.

**Summarization needs special handling, not a bigger model.** Below Medium the
failure is categorical: models answer in prose and ignore the schema. Either
that task goes to a Medium-or-larger model, or it stops demanding JSON and
takes a plain string, which costs nothing and would let a 0.5B model do it.

**Safety routing is not the same as quality routing.** The gate eliminates 10
of 15 models including the top scorer, and it cuts across size. Any prompt
carrying user-controlled free text has to go to a model from the passing list
regardless of what the quality numbers say.

---

## 7. Cost analysis (Part 2)

All figures come from the Part 2 cells of the notebook. The two 90-row tables
are saved as `local_hosting_costs.csv` and `hf_api_costs.csv`, and the
side-by-side as `cost_comparison.csv`. Prices were retrieved on 2026-10-28.

### 7.1 Token usage per user (Step 2.1)

A daily Beacon user triggers each AI job once: the answer is screened, a
resume or note is read, the answer is summarised, a weekly plan is written and
readiness is forecast. That is one request of each prompt type, five per user
per day.

| Prompt type | Input tokens (measured) | Output tokens (measured, all models) |
|---|---|---|
| Classification | 255 | 25 |
| Structured extraction | 266 | 31 |
| Summarization | 241 | 32 |
| Text generation | 344 | 82 |
| Prediction | 348 | 26 |
| **Per user per day** | **1,454** | **133-431, by model** |

Input tokens were counted by tokenizing the 25 rendered prompts. Output
tokens are each model's own `tokens/sec x latency`. That puts the average at
**1,587-1,884 tokens per user**, or **317-377 per request**, close to the
brief's example of 500. Outputs differ by model because verbose models cost
more. TinyLlama writes 431 output tokens a day per user against Qwen3-4B's
138, so the weakest model is also the most expensive to serve per user.

### 7.2 Total token load (Step 2.2)

| Traffic category | DAU | Daily token load |
|---|---|---|
| Prototype | 1,000 | 1.6M - 1.9M |
| Early Startup | 10,000 | 16M - 19M |
| Growing Product | 100,000 | 159M - 188M |
| Large Platform | 1,000,000 | 1.6B - 1.9B |
| Mass Consumer App | 10,000,000 | 16B - 19B |
| Global Platform | 100,000,000 | 159B - 188B |

### 7.3 Local hosting (Step 2.3)

**The machine.** The brief's 16-core / GPU / 64 GB configuration is exactly
an AWS **g5.4xlarge**: 16 vCPU, 64 GiB RAM and one NVIDIA A10G with 24 GB. It
costs **$1.624/hour** on demand, which is **$1,169.28/month**. Every one of
the 15 models fits in 24 GB (the largest is 8 GB in bf16), so a machine's
limit is throughput, not memory.

**Throughput is the one estimated input.** Our tokens/sec figures are
single-stream on an M4 Pro. A GPU server batches many requests at once. We
anchor on one published measurement: Qwen2.5-3B under vLLM reached 2,715
output tok/s at 50 concurrent requests on an RTX A5000. Scaled by memory
bandwidth to the A10G (600 vs 768 GB/s), that gives **~2,120 tok/s**. Each
other model is scaled by its measured speed relative to Qwen2.5-3B. Fleets
are planned at 60% utilisation and sized for an evening peak of 3x the daily
average. Machine counts should be read as **within roughly ±2x**.

Machines needed (excerpt; all 90 rows are in the notebook):

| Model | 1K | 10K | 100K | 1M | 10M | 100M |
|---|---|---|---|---|---|---|
| SmolLM2-135M | 1 | 1 | 1 | 2 | 20 | 191 |
| Qwen2.5-0.5B | 1 | 1 | 1 | 2 | 13 | 121 |
| Qwen2.5-1.5B | 1 | 1 | 1 | 3 | 22 | 215 |
| Qwen2.5-3B | 1 | 1 | 1 | 4 | 40 | 397 |
| Phi-3.5-mini | 1 | 1 | 1 | 7 | 61 | 606 |
| Qwen3-4B | 1 | 1 | 1 | 6 | 51 | 505 |

At 100M DAU, the Large tier needs a fleet of 505-608 GPU servers, about
$590K-$711K a month.

### 7.4 Hugging Face Inference API (Step 2.4)

Serverless **Hugging Face Inference Providers** bills per token at the
provider's price, with no Hugging Face markup. It needs **no GPU machines of
our own** (the application servers exist in both designs and cancel out).
Each local model is compared with the closest priced model on the router:

| Local models | Comparable paid model on Hugging Face | Price per 1M tokens (in / out) |
|---|---|---|
| Qwen3-4B-Instruct-2507 | Qwen/Qwen3-4B-Instruct-2507 via nscale (the same model) | $0.01 / $0.03 |
| Phi-3.5-mini, Phi-4-mini | google/gemma-3-4b-it via deepinfra | $0.05 / $0.10 |
| All 12 models under 3.5B | ibm-granite/granite-4.2-3b via deepinfra | $0.03 / $0.12 |

**No provider sells anything under 3B per token.** Qwen2.5-0.5B, Llama-3.2-1B
and similar models are listed only on a provider that publishes no price. The
small local models are therefore compared with a larger API model, which
favours local hosting in the comparison.

API cost per month, for comparison with the machine table:

| Model | 1K | 10K | 100K | 1M | 10M | 100M |
|---|---|---|---|---|---|---|
| Qwen2.5-1.5B → granite-4.2-3b | $1.86 | $18.60 | $186 | $1,860 | $18,597 | $185,973 |
| Qwen3-4B → Qwen3-4B | $0.56 | $5.60 | $56 | $560 | $5,601 | $56,008 |

### 7.5 Analysis (Step 2.5)

**1. At what scale is local hosting cheaper?**

**Only for the sub-1B models, and only from about 1M-10M DAU.** SmolLM2-135M
becomes cheaper locally at Large Platform (local/API = 0.9). Qwen2.5-0.5B,
SmolLM2-360M and LFM2-700M become cheaper at Mass Consumer App (0.7-0.9).
Once a fleet is large, both costs grow linearly, so the question reduces to a
cost per million output tokens:

| Model | Local, on demand | Local, 1-year reserved | API (output-equivalent) |
|---|---|---|---|
| Qwen2.5-0.5B | $0.30 | $0.19 | $0.40 |
| Qwen2.5-1.5B | $0.55 | $0.35 | $0.41 |
| Qwen2.5-3B | $1.06 | $0.67 | $0.42 |
| Qwen3-4B | $1.43 | $0.90 | $0.14 |

With a one-year reservation ($1.023/hour), the 1.1-1.5B models (TinyLlama,
LFM2-1.2B, OLMo-2-1B, Qwen2.5-1.5B) also tip to local at scale, for example
Qwen2.5-1.5B at $0.35 vs $0.41. Nothing at or above 2B ever does. Qwen3-4B is the
clearest case: the identical model costs **10.5x more to host ourselves**
than to rent per token, even at 100M DAU.

**2. At what scale is API usage cheaper?**

**At every scale below about 0.5M DAU for every model, and at every scale for
every model of 2B and above.** A single GPU costs $1,169 a month whether it
serves one user or 600,000. The API bill only reaches that figure at
**409K-653K DAU** for 14 of the 15 models, and at **2.1M DAU** for Qwen3-4B.
Below that, a local server is overhead: at Beacon's prototype scale it costs
628x the API bill for Qwen2.5-1.5B.

**3. When would we switch architecture?**

Beacon starts **API-only** and changes only when one of these triggers fires:

| Trigger | Switch to | Why |
|---|---|---|
| Personal data at volume (resumes) | One local GPU for extraction only | Policy, not price: resumes stay on Beacon's machines (section 8) |
| DAU > ~1M and a sub-1B model is good enough for a job | Local fleet for that job, on reserved instances | The only measured case where local is cheaper |
| API price rises 3x+ or rate limits bind | Local fleet for the narrow jobs | The break-even moves down in proportion |
| API outage risk becomes unacceptable | Keep a small local fleet as a fallback | Resilience, priced in section 8 |

Throughput is the one estimated input. If a GPU were really 2x faster than
assumed, every local figure would halve. Qwen2.5-1.5B would then be cheaper
locally from about 10M DAU ($0.27 vs $0.41 per 1M), but the Large tier would
still not be ($0.70 vs $0.14 for Qwen3-4B). The
conclusion for models of 2B and above does not depend on that estimate.

---

## 8. Routing design (Part 3)

### 8.1 What routing has to respect

Two rules come from Parts 1 and 2 before cost does:

1. **Personal data stays on Beacon's machines.** Structured extraction reads
   resumes, so it is always local. This is the only reason a local GPU exists
   at all, since section 7 showed the API is cheaper on price.
2. **The injection gate is per prompt type.** Section 6.3 treats obeying an
   injected instruction as disqualifying. The raw replies show where each
   model failed: **the three larger Qwen models resisted on four types and
   failed only on summarization**, and only Qwen2.5-0.5B passed all five. Qwen3-4B replied `{"summary": "HACKED"}`. So the Qwen API
   may serve classification, generation and prediction, but summarization
   goes only to a model that passed: **granite-3.1-2b** (9.26, 100% parsed),
   run locally.

Within those rules, cost decides. GPUs are a fixed daily cost of $38.98 each,
and the API is pay-per-token at $0.01/$0.03 per 1M. Every request the rules
allow therefore goes to the API, and the routing decisions are about keeping
the local fleet small.

| Role | Model | Why |
|---|---|---|
| Local triage | Qwen2.5-0.5B-Instruct | Fastest model above 8 (8.63); passed the gate on all five types |
| Local workhorse | Qwen2.5-1.5B-Instruct | 9.6 on classification and extraction; resisted injection on both |
| Local gate-safe | granite-3.1-2b-instruct | Gate-safe everywhere; 9.26 on summarization |
| Local predictor | Qwen2.5-3B-Instruct | 9.38 on prediction, second only to Phi-3.5-mini (9.68) at 40% less latency |
| Hugging Face API | Qwen/Qwen3-4B-Instruct-2507 (nscale) | 9.7-9.8 on classification, extraction and generation; the exact model benchmarked |

### 8.2 Five scenarios (Step 3.1)

| Scenario | Description in Beacon | Routing condition that detects it |
|---|---|---|
| **Normal operation** | Everyday traffic: answers screened, resumes read, plans written | Default |
| **Peak usage hours** | Sunday night before interview week: 3x the normal peak rate | System load: local queue depth above capacity |
| **High-complexity queries** | Long resumes and multi-skill plans: 2x extraction and summaries, 3x plans | Prompt length and query complexity (input tokens, number of skills) |
| **Cost optimization** | Shrink the GPU fleet once traffic is stable | Daily request volume and monthly GPU spend |
| **System overload / API outage** | The provider returns errors or times out while the fleet is at its normal size | API error rate and timeouts |

### 8.3 Routing strategies (Step 3.2)

| Scenario | Routing strategy | Local models used | Hugging Face model used | Expected benefit |
|---|---|---|---|---|
| Normal operation | Extraction on the local workhorse (unparseable replies retried on granite); summaries on local granite; classification, plans and forecasts on the API | Qwen2.5-1.5B, granite-3.1-2b | Qwen3-4B-Instruct-2507 | Smallest compliant fleet, top-tier quality on the API jobs |
| Peak usage hours | Extraction drops to the 2x-faster 0.5B triage model; API jobs unchanged; summaries beyond capacity fall back to Beacon's rules; extraction queues, never leaves | Qwen2.5-0.5B, granite-3.1-2b | Qwen3-4B-Instruct-2507 | Absorbs 3x load with no extra GPUs and no policy breach |
| High-complexity queries | Long resumes go to the larger gate-safe granite, still local; long plans and forecasts to the API | granite-3.1-2b | Qwen3-4B-Instruct-2507 | Best quality on the hard inputs where size helps |
| Cost optimization | The smallest model that passes each local job: 0.5B for extraction and summaries, unparseable replies retried on granite | Qwen2.5-0.5B (+ granite retries) | Qwen3-4B-Instruct-2507 | 40% fewer GPUs for a small quality cost |
| System overload / API outage | Everything local on the existing fleet: 1.5B for screening, extraction and plans, 3B for forecasts, granite for summaries; overflow to the rules engine | Qwen2.5-1.5B, Qwen2.5-3B, granite-3.1-2b | None (unreachable) | The service stays up with degraded quality |

The notebook prints the full per-type routing table, and the code
`assert`s that no personal-data request and no summary is ever sent to the
API.

### 8.4 Simulated results (Mass Consumer App: 10M DAU, 50M requests/day)

At 1M DAU the whole local share fits on one GPU, so scenarios only differ in
fleet size at the next scale up. **Measured inputs:** quality, parse rate,
latency and output tokens per model and type. **Sourced inputs:** prices.
**Assumed inputs:**
- API latency is 0.35 s + output tokens at 120 tok/s.
- The rules fallback scores 5/10 at 0.05 s.
- Local latencies are M4 Pro single-stream figures, an upper bound for an A10G.

| Scenario | GPUs | $/day | Quality | Mean latency | Single-model baseline (all granite, gate-safe) |
|---|---|---|---|---|---|
| Normal operation | 10 | **$514** | **9.39** | 0.87 s | 41 GPUs, $1,598, 9.23, 2.02 s |
| Peak (3x) | 10 (fixed) | $514 | 8.79 | 0.77 s | 41 GPUs, $1,681, 8.74, 1.57 s |
| High complexity | 14 | $672 | 9.41 | 1.07 s | 51 GPUs, $1,988, 9.35, 2.42 s |
| Cost optimization | **6** | **$358** | 9.15 | 0.67 s | 41 GPUs, $1,598, 9.23, 2.02 s |
| API outage | 10 (fixed) | $390 | 7.15 | 0.82 s | 41 GPUs, $1,598, 9.23, 2.02 s |

For reference, sending everything to the API would cost **$187/day with no
GPUs**. That design is not allowed under the two rules above. The
$327/day difference from normal routing is what the privacy and safety
rules cost at this scale.

### 8.5 Evaluating the strategy (Step 3.3)

**How routing improves latency.** In normal operation the mean falls from
2.02 s for the single-model design to **0.87 s**, a 57% cut, for three
reasons:
- **Each request goes to the fastest model that does that job well.**
  Extraction runs on a 1.5B model (0.60 s) instead of a 2B one (1.20 s).
- **The API handles the long generations.** The 82-token plans are the
  slowest job locally (2.38 s on the 1.5B model, 4.31 s on granite). Even
  with 0.35 s of network overhead, a hosted model returns them faster.
- **Under a 3x peak, latency does not explode.** Mean latency actually drops
  to 0.77 s. The fleet stops trying to serve everything: summaries beyond
  capacity get a fast rule-based answer, and extraction queues on the
  smaller, 2x-faster triage model. A single-model fleet sized for normal
  load would queue every request type.

**How routing reduces cost.**
- **Fleet size is the cost.** At 10M DAU a GPU is $38.98/day, while the API
  share costs about $124/day in total. Routing sends 60% of requests to the
  API, cutting the fleet from 41 to 10 GPUs. That takes the bill from
  $1,598 to $514/day (**-68%**) while still meeting both policies.
- **The cost-optimization strategy saves another 30%** ($358/day, 6 GPUs) by
  running the smallest model that passes each local job. The trade-off is
  visible: quality drops by 0.24, and 4% of replies fail to parse and are
  retried on granite.
- **Routing on confidence is cheap.** Retrying an unparseable reply locally
  costs a fraction of a second. Routing every request to a bigger model in
  case it might fail costs a fleet.

**How routing maintains quality.**
- **Normal routing scores 9.39 against 9.23 for the single-model fleet.** It
  is higher, not lower, because each job goes to the model that scored best
  on that job in Part 1, and no single model wins every type.
- **The injection gate is never traded away.** Summaries never reach the
  model that obeyed the injected instruction, and resumes never leave
  Beacon's machines. Both are enforced by `assert`, not by convention.
- **Low-confidence replies are retried.** The cost-optimization 0.5B model
  fails to parse 20% of summaries. Those are retried on granite, so the user
  gets a valid summary, not an error.
- **Under failure, quality degrades predictably.** During an API outage, the
  10-GPU fleet serves everything it can at local quality. The 65% it cannot
  absorb gets the rule-based answer Beacon already has, so the mean falls to
  7.15 but every request still gets an answer. Holding 9.23 through an
  outage would mean keeping 41 GPUs, 4x the fleet, idle the rest of the time.
  That costs $1,208 a day (31 extra GPUs) as insurance against something that rarely happens.

**Two improvements the simulation points to.** Summaries are not on the
user's critical path, since they feed the history page. Deferring them during
peaks, instead of falling back to rules, would keep peak quality close to
the normal 9.39 at no extra cost. And because the API is cheap, the next step for routing is
contractual rather than technical: a data-processing agreement covering
resumes would let extraction move to the API too, and remove most of the
fleet.
