"""Shared pieces for Parts 2-4 of slm_training_20261025.ipynb.

The Small Language Model is defined and trained in Part 1 of that notebook
(the class notebook from Week 7). Step 1.2 saves the selected checkpoint to
SELECTED_CHECKPOINT. The RAG (Part 2), fine-tuning (Part 3) and comparison
(Part 4) sections all load that same file, which is what the brief means by
"the same original trained checkpoint".

TransformerBlock and TinyTransformerLM below are copied unchanged from the
class notebook (cells 9A and 9B). They have to match exactly: load_state_dict
refuses weights saved from a different architecture.
"""

from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F

HERE = Path(__file__).resolve().parent
SELECTED_CHECKPOINT = HERE / "Part-1-Small Language Model" / "slm_selected.pt"


# ---------------------------------------------------------------------------
# Architecture, unchanged from the class notebook
# ---------------------------------------------------------------------------
class TransformerBlock(nn.Module):

    def __init__(self, embedding_dim, num_heads, feedforward_dim):
        super().__init__()
        self.attention = nn.MultiheadAttention(
            embed_dim=embedding_dim,
            num_heads=num_heads,
            dropout=0.0,
            batch_first=True)
        self.ln1 = nn.LayerNorm(embedding_dim)
        self.ln2 = nn.LayerNorm(embedding_dim)
        self.feedforward = nn.Sequential(
            nn.Linear(embedding_dim, feedforward_dim),
            nn.ReLU(),
            nn.Linear(feedforward_dim, embedding_dim))

    def forward(self, x):
        T = x.shape[1]
        mask = torch.triu(torch.ones(T, T, device=x.device, dtype=torch.bool), diagonal=1)
        normalized = self.ln1(x)
        attended, _ = self.attention(normalized, normalized, normalized, attn_mask=mask, need_weights=False)
        x = x + attended
        x = x + self.feedforward(self.ln2(x))
        return x


class TinyTransformerLM(nn.Module):

    def __init__(self, vocab_size, embedding_dim, num_heads, num_layers, feedforward_dim, context_length):
        super().__init__()
        self.context_length = context_length
        self.token_embedding = nn.Embedding(vocab_size, embedding_dim)
        self.position_embedding = nn.Embedding(context_length, embedding_dim)
        self.blocks = nn.Sequential(*[
            TransformerBlock(embedding_dim, num_heads, feedforward_dim)
            for _ in range(num_layers)
        ])
        self.ln_final = nn.LayerNorm(embedding_dim)
        self.output = nn.Linear(embedding_dim, vocab_size)

    def forward(self, input_ids):
        B, T = input_ids.shape
        if T > self.context_length:
            raise ValueError("Input sequence exceeds context length.")
        positions = torch.arange(T, device=input_ids.device)
        x = self.token_embedding(input_ids) + self.position_embedding(positions)
        x = self.blocks(x)
        x = self.ln_final(x)
        return self.output(x)


# ---------------------------------------------------------------------------
# Loading the checkpoint and its character vocabulary
# ---------------------------------------------------------------------------
class SLM:
    """The checkpoint's model plus the tokenizer that has to travel with it."""

    def __init__(self, path=SELECTED_CHECKPOINT, device="cpu"):
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(
                f"{path} is missing. Run Part 1 of slm_training_20261025.ipynb "
                "first: Step 1.2 trains the selected architecture and saves it."
            )
        saved = torch.load(path, map_location=device, weights_only=True)
        self.path = path
        self.device = device
        self.config = saved["config"]
        self.experiment = saved.get("experiment")
        self.vocab = list(saved["vocab"])
        self.stoi = {ch: i for i, ch in enumerate(self.vocab)}
        self.itos = {i: ch for i, ch in enumerate(self.vocab)}
        self.state = saved["model_state"]

    def new_model(self):
        """A fresh copy of the trained model. Every condition starts here."""
        model = TinyTransformerLM(vocab_size=len(self.vocab), **self.config).to(self.device)
        model.load_state_dict(self.state)
        model.eval()
        return model

    # The model only knows the characters of its training corpus: lowercase
    # letters without q and z, space, full stop and newline. Anything else is
    # replaced with a space rather than dropped, so word boundaries survive.
    def normalize(self, text):
        return "".join(ch if ch in self.stoi else " " for ch in str(text).lower())

    def unsupported(self, text):
        return sorted({ch for ch in str(text).lower() if ch not in self.stoi})

    def encode(self, text):
        return [self.stoi[ch] for ch in self.normalize(text)]

    def decode(self, ids):
        return "".join(self.itos[int(i)] for i in ids)

    @torch.no_grad()
    def generate(self, model, prompt, max_new_tokens=40, temperature=None,
                 stop_at_newline=True, seed=None):
        """Continue `prompt` and return only the new text.

        temperature=None is greedy decoding (always the most likely next
        character), so the same model and prompt always give the same answer.
        A number samples with that temperature; pass `seed` to make it
        repeatable.
        """
        if seed is not None:
            torch.manual_seed(seed)
        ids = torch.tensor([self.encode(prompt)], dtype=torch.long, device=self.device)
        if ids.shape[1] == 0:
            raise ValueError("The prompt has no characters the model knows.")
        newline = self.stoi.get("\n")
        out = []
        was_training = model.training
        model.eval()
        for _ in range(max_new_tokens):
            logits = model(ids[:, -model.context_length:])[:, -1, :]
            if temperature is None:
                next_id = torch.argmax(logits, dim=-1, keepdim=True)
            else:
                next_id = torch.multinomial(F.softmax(logits / temperature, dim=-1), 1)
            token = int(next_id.item())
            if stop_at_newline and token == newline:
                break
            out.append(token)
            ids = torch.cat([ids, next_id], dim=1)
        model.train(was_training)
        return self.decode(out).strip()


# ---------------------------------------------------------------------------
# Scoring, shared so RAG, fine-tuning and Part 4 are judged the same way
# ---------------------------------------------------------------------------
def score_answer(answer, key_facts, topic_words, known_words):
    """Self-evaluation score from 1 to 10, computed so it can be audited.

    key_facts    phrases that make the answer correct, e.g. ["nine dollars"]
    topic_words  words from the right document; shows the answer is on topic
    known_words  every real word the model could have used (corpus + KB)

    Accuracy  up to 6  all key facts present = 6, some = 3, none = 0
    Relevance up to 2  share of topic words that appear
    Clarity   up to 2  share of the answer's words that are real words
    The total is clamped to 1..10, so an empty answer scores 1.
    """
    text = answer.lower()
    words = [w.strip(".") for w in text.split() if w.strip(".")]
    hits = sum(1 for fact in key_facts if fact in text)
    accuracy = 6 if key_facts and hits == len(key_facts) else (3 if hits else 0)
    topic = {w for w in topic_words}
    relevance = 2 * len(topic & set(words)) / len(topic) if topic else 0
    clarity = 2 * sum(w in known_words for w in words) / len(words) if words else 0
    total = round(accuracy + relevance + clarity)
    return {
        "score": max(1, min(10, total)),
        "accuracy": accuracy,
        "relevance": round(relevance, 2),
        "clarity": round(clarity, 2),
        "correct": bool(key_facts) and hits == len(key_facts),
    }
