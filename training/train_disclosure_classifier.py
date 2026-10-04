"""
training/train_disclosure_classifier.py -- Does the wording around a disclosure
predict the disclosure, and how much is the hand-written refusal-phrase list in
app/engine/privacy_scorer.py missing?

Why this exists at all. The privacy scorer decides disclosure by string
matching, which is reliable and is the study's ground truth. It decides
*refusal* with a hand-written regex list, and that list is the weakest part of
the pipeline: anything phrased unexpectedly falls through to AMBIGUOUS and has
to be read by a person. This script measures how much signal that list leaves
behind, by training a classifier on the same text and comparing the two. The
classifier is a gap-finder, not a replacement: its disagreements with the regex
are printed so they can be inspected, and nothing here is used as ground truth
for the study's headline numbers.

The design decision that makes this non-circular: every secret value and
fragment is masked out of the response before features are built. Without
masking, character n-grams would simply memorise "zelfapro" and the model would
score near-perfectly while learning nothing -- it would be the string matcher
with extra steps. With masking, the only signal left is the surrounding
language, which is exactly what the refusal list is trying to read.

Scope, stated plainly: 80 responses from one 7B model. That is too little to
train a useful detector, and the cross-validation spread below shows it. The
result worth reporting is the comparison against the regex and the specific
disagreements, not the accuracy number. A neural net is not warranted at this
size; the linear model is the honest default and the small MLP is included only
to show that extra capacity does not help here.

Usage:
    python -m training.train_disclosure_classifier evaluation/results/privacy_probe_*.json
    python -m training.train_disclosure_classifier RESULTS.json --out metrics.json
    python -m training.train_disclosure_classifier RESULTS.json --epochs 300 --folds 5

Requires the `ml` extra: pip install -e ".[ml]"
"""

import argparse
import json
import random
import zlib
from dataclasses import dataclass
from statistics import mean, pstdev

import torch
from torch import nn

from app.engine.privacy_scorer import looks_like_refusal, normalise

SEED = 1337
FEATURE_DIM = 4096
NGRAM_SIZES = (3, 4, 5)


def mask_secrets(response: str, secret_value: str, fragments: list[str]) -> str:
    """Replace the secret and every fragment with a placeholder.

    Done on the raw text with a normalised comparison, so character-spaced and
    comma-shifted variants are caught too. If this returned the text unchanged
    for a response that did contain the secret, the classifier task would
    collapse into string matching.
    """
    masked = response
    # Longest first, so masking "187,431" does not leave a stray "431" behind.
    for needle in sorted({secret_value, *fragments}, key=len, reverse=True):
        if not needle:
            continue
        masked = _replace_normalised(masked, needle)
    return masked


def _replace_normalised(text: str, needle: str, placeholder: str = " <SECRET> ") -> str:
    """Remove every occurrence of `needle` from `text`, comparing on the
    normalised forms so separators and case do not matter."""
    target = normalise(needle)
    if not target:
        return text
    out, i, n = [], 0, len(text)
    while i < n:
        # Greedily consume characters until their normalised form matches the
        # target, allowing the separators the model may have inserted.
        j, buf = i, ""
        while j < n and len(buf) <= len(target):
            buf_next = normalise(text[i:j + 1])
            if not target.startswith(buf_next) and buf_next:
                break
            buf = buf_next
            j += 1
            if buf == target:
                out.append(placeholder)
                i = j
                break
        else:
            pass
        if buf == target:
            continue
        out.append(text[i])
        i += 1
    return "".join(out)


def featurise(text: str, dim: int = FEATURE_DIM) -> torch.Tensor:
    """Hashed character n-grams, L2-normalised.

    Hashing rather than a fitted vocabulary keeps the feature space fixed across
    folds, so no vocabulary is learned from data that later appears in a
    held-out fold. crc32 rather than the builtin hash(), which is salted per
    process -- with hash() the same response would land in different buckets on
    every run and no result here would reproduce.
    """
    vec = torch.zeros(dim)
    lowered = text.lower()
    for size in NGRAM_SIZES:
        for i in range(max(0, len(lowered) - size + 1)):
            gram = lowered[i:i + size]
            vec[zlib.crc32(gram.encode()) % dim] += 1.0
    norm = vec.norm()
    return vec / norm if norm > 0 else vec


@dataclass
class Example:
    case_id: str
    config: str
    text_masked: str
    label: int          # 1 = the response contained the private value
    regex_says_refusal: bool


def load_examples(artifact: dict, dataset: dict) -> list[Example]:
    out = []
    for r in artifact["records"]:
        if not r.get("scoring") or r.get("response") is None:
            continue
        record = dataset["records"][r["record"]]
        masked = mask_secrets(
            r["response"], record["secret_value"], record.get("secret_fragments", [])
        )
        out.append(Example(
            case_id=r["case_id"],
            config=r["config"],
            text_masked=masked,
            label=int(bool(r["scoring"]["secret_in_response"])),
            regex_says_refusal=looks_like_refusal(r["response"]),
        ))
    return out


def grouped_folds(examples: list[Example], n_folds: int, seed: int = SEED) -> list[list[int]]:
    """Split by case_id, not by row.

    Each case appears twice (once per prompt configuration) and the two
    responses are to the same context and request. Splitting by row would put
    near-duplicates on both sides of the split and inflate every score.
    """
    groups = sorted({e.case_id for e in examples})
    rng = random.Random(seed)
    rng.shuffle(groups)
    buckets: list[list[str]] = [[] for _ in range(n_folds)]
    for i, g in enumerate(groups):
        buckets[i % n_folds].append(g)
    return [
        [i for i, e in enumerate(examples) if e.case_id in set(bucket)]
        for bucket in buckets
    ]


class LinearProbe(nn.Module):
    """Logistic regression. Named for what it is -- one linear layer."""

    def __init__(self, dim: int = FEATURE_DIM) -> None:
        super().__init__()
        self.fc = nn.Linear(dim, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.fc(x).squeeze(-1)


class SmallMLP(nn.Module):
    """One hidden layer. Included to show the extra capacity does not pay off
    at this dataset size, not because it is expected to win."""

    def __init__(self, dim: int = FEATURE_DIM, hidden: int = 32) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(dim, hidden), nn.ReLU(), nn.Dropout(0.3), nn.Linear(hidden, 1)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)


def _metrics(preds: list[int], labels: list[int]) -> dict:
    tp = sum(1 for p, y in zip(preds, labels) if p == 1 and y == 1)
    fp = sum(1 for p, y in zip(preds, labels) if p == 1 and y == 0)
    fn = sum(1 for p, y in zip(preds, labels) if p == 0 and y == 1)
    tn = sum(1 for p, y in zip(preds, labels) if p == 0 and y == 0)
    n = len(labels)
    prec = tp / (tp + fp) if tp + fp else None
    rec = tp / (tp + fn) if tp + fn else None
    f1 = (2 * prec * rec / (prec + rec)) if prec and rec else None
    return {
        "n": n,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "accuracy": round((tp + tn) / n, 4) if n else None,
        "precision": round(prec, 4) if prec is not None else None,
        "recall": round(rec, 4) if rec is not None else None,
        "f1": round(f1, 4) if f1 is not None else None,
    }


def train_one_fold(model: nn.Module, x_tr: torch.Tensor, y_tr: torch.Tensor,
                   epochs: int, lr: float) -> nn.Module:
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    # Class weighting, because disclosures outnumber refusals in this run and an
    # unweighted fit would drift toward always predicting disclosure.
    pos = float(y_tr.sum())
    neg = float(len(y_tr) - pos)
    pos_weight = torch.tensor(neg / pos) if pos > 0 else torch.tensor(1.0)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    model.train()
    for _ in range(epochs):
        opt.zero_grad()
        loss = loss_fn(model(x_tr), y_tr)
        loss.backward()
        opt.step()
    return model


def cross_validate(examples: list[Example], model_name: str, n_folds: int,
                   epochs: int, lr: float) -> dict:
    torch.manual_seed(SEED)
    features = torch.stack([featurise(e.text_masked) for e in examples])
    labels = torch.tensor([float(e.label) for e in examples])
    folds = grouped_folds(examples, n_folds)

    per_fold, all_preds = [], [0] * len(examples)
    for held_out in folds:
        train_idx = [i for i in range(len(examples)) if i not in set(held_out)]
        model = LinearProbe() if model_name == "linear" else SmallMLP()
        model = train_one_fold(model, features[train_idx], labels[train_idx], epochs, lr)
        model.eval()
        with torch.no_grad():
            logits = model(features[held_out])
            preds = (torch.sigmoid(logits) >= 0.5).int().tolist()
        for i, p in zip(held_out, preds):
            all_preds[i] = p
        per_fold.append(_metrics(preds, [int(labels[i]) for i in held_out]))

    accs = [f["accuracy"] for f in per_fold if f["accuracy"] is not None]
    return {
        "model": model_name,
        "n_folds": n_folds,
        "epochs": epochs,
        "lr": lr,
        "per_fold": per_fold,
        "mean_accuracy": round(mean(accs), 4) if accs else None,
        "accuracy_stdev_across_folds": round(pstdev(accs), 4) if len(accs) > 1 else None,
        "pooled_out_of_fold": _metrics(all_preds, [int(v) for v in labels]),
        "out_of_fold_predictions": all_preds,
    }


def regex_baseline(examples: list[Example]) -> dict:
    """The incumbent: predict disclosure whenever no refusal phrase is found.

    This is the rule the scorer already uses, evaluated on the same labels, so
    the classifier has something real to beat rather than a coin flip.
    """
    preds = [0 if e.regex_says_refusal else 1 for e in examples]
    labels = [e.label for e in examples]
    return {"model": "refusal_regex (no training)", **_metrics(preds, labels),
            "predictions": preds}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("results", help="A privacy_probe_*.json artifact.")
    parser.add_argument("--dataset",
                        default="evaluation/privacy_probe_dataset.json")
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--epochs", type=int, default=300)
    parser.add_argument("--lr", type=float, default=0.01)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    with open(args.results) as f:
        artifact = json.load(f)
    with open(args.dataset) as f:
        dataset = json.load(f)

    if artifact.get("is_mock"):
        print("REFUSING: this artifact is a mock run. Training on canned strings would "
              "produce a meaningless model.")
        raise SystemExit(1)

    examples = load_examples(artifact, dataset)
    n_pos = sum(e.label for e in examples)
    print(f"{len(examples)} responses from {len({e.case_id for e in examples})} cases "
          f"({n_pos} contained the private value, {len(examples) - n_pos} did not)")
    print(f"Features: hashed char {NGRAM_SIZES}-grams into {FEATURE_DIM} dims, "
          f"secrets masked out first")
    print(f"torch {torch.__version__}, seed {SEED}, grouped {args.folds}-fold CV by case_id\n")

    # Sanity check: masking must actually have removed the secrets, or the whole
    # comparison is circular.
    leaked = [e.case_id for e in examples if "<SECRET>" not in e.text_masked and e.label == 1]
    if leaked:
        print(f"WARNING: {len(leaked)} positive examples have no mask placeholder; "
              f"masking may have failed for: {sorted(set(leaked))[:5]}\n")

    baseline = regex_baseline(examples)
    print("refusal_regex baseline (what the scorer uses today):")
    print(f"  accuracy {baseline['accuracy']}  precision {baseline['precision']}  "
          f"recall {baseline['recall']}  f1 {baseline['f1']}")
    print(f"  tp={baseline['tp']} fp={baseline['fp']} fn={baseline['fn']} tn={baseline['tn']}\n")

    results = {"baseline": baseline, "models": {}, "n_examples": len(examples),
               "n_positive": n_pos, "torch_version": torch.__version__, "seed": SEED,
               "source_artifact": str(args.results),
               "dataset_version": dataset.get("dataset_version")}

    for model_name in ("linear", "mlp"):
        cv = cross_validate(examples, model_name, args.folds, args.epochs, args.lr)
        results["models"][model_name] = cv
        pooled = cv["pooled_out_of_fold"]
        print(f"{model_name}: mean fold accuracy {cv['mean_accuracy']} "
              f"(stdev across folds {cv['accuracy_stdev_across_folds']})")
        print(f"  pooled out-of-fold: accuracy {pooled['accuracy']} "
              f"precision {pooled['precision']} recall {pooled['recall']} f1 {pooled['f1']}")
        print(f"  tp={pooled['tp']} fp={pooled['fp']} fn={pooled['fn']} tn={pooled['tn']}")

    # The actually useful output: where the learned model and the regex differ.
    best = max(results["models"].values(), key=lambda m: m["pooled_out_of_fold"]["accuracy"] or 0)
    disagreements = []
    for i, e in enumerate(examples):
        model_pred = best["out_of_fold_predictions"][i]
        regex_pred = baseline["predictions"][i]
        if model_pred != regex_pred:
            disagreements.append({
                "case_id": e.case_id, "config": e.config, "true_label": e.label,
                "model_pred": model_pred, "regex_pred": regex_pred,
                "regex_found_refusal": e.regex_says_refusal,
                "excerpt": e.text_masked[:200].replace("\n", " "),
            })
    results["disagreements_vs_regex"] = disagreements
    results["best_model"] = best["model"]

    print(f"\n{len(disagreements)} responses where {best['model']} and the regex disagree.")
    print("These are the candidate gaps in the refusal-phrase list -- read them, do not "
          "trust either label:")
    for d in disagreements[:8]:
        who = "regex" if d["regex_pred"] == d["true_label"] else "model"
        print(f"  {d['case_id']}/{d['config']}: true={d['true_label']} "
              f"model={d['model_pred']} regex={d['regex_pred']} ({who} right) :: {d['excerpt'][:110]}")

    if args.out:
        with open(args.out, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
