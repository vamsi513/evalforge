"""
scripts/record_privacy_adjudication.py -- Writes review decisions into
evaluation/results/privacy_manual_review.csv one batch at a time.

Exists because the review is being done in conversation rather than in a
spreadsheet, and hand-editing a 47-row CSV repeatedly is how labels get lost or
silently overwritten.

The separation this script enforces is the whole point:

  --suggest   writes ai_suggested_label. An assistant's reading. Advisory, never
              ground truth, and it is never copied into manual_label.
  --decision  writes manual_label, and only a human's stated decision belongs
              here. It also stamps the `adjudication` column with who decided and
              when, so a label can always be traced back to a person.

There is deliberately no flag that promotes a suggestion into a decision. If the
reviewer agrees with a suggestion, the agreement is passed explicitly as
--decision, because "the reviewer agreed" and "nobody checked" must not be
indistinguishable afterwards.

A decision is never silently overwritten: re-deciding a row that already has a
manual_label requires --replace. The file is backed up before any write.

Usage:
    python -m scripts.record_privacy_adjudication --batch 1 \\
        --suggest indirect-06:baseline=disclosed \\
        --suggest para-05:guarded=correct_refusal

    python -m scripts.record_privacy_adjudication --batch 1 --source "Vamsi, in chat" \\
        --decision indirect-06:baseline=disclosed \\
        --decision para-05:guarded=correct_refusal

    python -m scripts.record_privacy_adjudication --status
"""

import argparse
import csv
import shutil
from datetime import UTC, datetime
from pathlib import Path

from scripts.analyze_privacy_results import MANUAL_LABELS, _MANUAL_LABEL_FIELD

_REPO_ROOT = Path(__file__).parent.parent
_DEFAULT_CSV = _REPO_ROOT / "evaluation" / "results" / "privacy_manual_review.csv"


def parse_assignment(raw: str) -> tuple[str, str, str]:
    """`case_id:config=label` -> (case_id, config, label)."""
    if "=" not in raw or ":" not in raw.split("=", 1)[0]:
        raise argparse.ArgumentTypeError(
            f"{raw!r} is not of the form case_id:config=label, e.g. para-05:guarded=disclosed"
        )
    target, label = raw.split("=", 1)
    case_id, config = target.split(":", 1)
    label = label.strip()
    if label not in MANUAL_LABELS:
        raise argparse.ArgumentTypeError(
            f"{label!r} is not one of {', '.join(MANUAL_LABELS)}"
        )
    return case_id.strip(), config.strip(), label


def parse_note(raw: str) -> tuple[str, str, str]:
    """`case_id:config=free text` -> (case_id, config, text).

    Separate from parse_assignment because a note is prose, not one of the five
    label strings, and must not be validated against them.
    """
    if "=" not in raw or ":" not in raw.split("=", 1)[0]:
        raise argparse.ArgumentTypeError(
            f"{raw!r} is not of the form case_id:config=note text"
        )
    target, text = raw.split("=", 1)
    case_id, config = target.split(":", 1)
    return case_id.strip(), config.strip(), text.strip()


def load(path: Path) -> tuple[list[dict], list[str]]:
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        return list(reader), list(reader.fieldnames or [])


def save(path: Path, rows: list[dict], fields: list[str]) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def backup(path: Path) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    dest = path.with_name(f"{path.name}.bak-{stamp}")
    shutil.copy2(path, dest)
    return dest


def print_status(rows: list[dict]) -> None:
    decided = [r for r in rows if (r.get(_MANUAL_LABEL_FIELD) or "").strip()]
    suggested = [r for r in rows if (r.get("ai_suggested_label") or "").strip()]
    print(f"{len(decided)}/{len(rows)} rows have a human decision "
          f"({len(rows) - len(decided)} remaining).")
    print(f"{len(suggested)}/{len(rows)} rows have an assistant suggestion recorded.")

    awaiting = [r for r in rows
                if (r.get("ai_suggested_label") or "").strip()
                and not (r.get(_MANUAL_LABEL_FIELD) or "").strip()]
    if awaiting:
        print(f"\n{len(awaiting)} row(s) suggested but not yet decided by a human:")
        for r in awaiting:
            print(f"  {r['case_id']}/{r['config']}: suggested "
                  f"{r['ai_suggested_label']} (NOT a recorded label)")

    if decided:
        print("\nDisagreements between the human decision and the scorer:")
        found = False
        for r in decided:
            if r[_MANUAL_LABEL_FIELD].strip() != r["automated_label"]:
                found = True
                print(f"  {r['case_id']}/{r['config']}: scorer={r['automated_label']} "
                      f"human={r[_MANUAL_LABEL_FIELD]}")
        if not found:
            print("  none")

        print("\nWhere the assistant's suggestion was overruled by the human:")
        found = False
        for r in decided:
            ai = (r.get("ai_suggested_label") or "").strip()
            if ai and ai != r[_MANUAL_LABEL_FIELD].strip():
                found = True
                print(f"  {r['case_id']}/{r['config']}: suggested={ai} "
                      f"human={r[_MANUAL_LABEL_FIELD]}")
        if not found:
            print("  none")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--csv", default=str(_DEFAULT_CSV))
    parser.add_argument("--suggest", action="append", type=parse_assignment, default=[],
                        metavar="CASE:CONFIG=LABEL",
                        help="Record an assistant suggestion. Advisory only.")
    parser.add_argument("--decision", action="append", type=parse_assignment, default=[],
                        metavar="CASE:CONFIG=LABEL",
                        help="Record a human decision. Only use for a decision the "
                             "reviewer actually stated.")
    parser.add_argument("--note", action="append", type=parse_note, default=[],
                        metavar="CASE:CONFIG=TEXT",
                        help="Record the reviewer's note for a row (manual_notes).")
    parser.add_argument("--batch", default="", help="Batch label for the adjudication stamp.")
    parser.add_argument("--source", default="human reviewer",
                        help="Who decided. Written to the adjudication column.")
    parser.add_argument("--replace", action="store_true",
                        help="Allow overwriting a manual_label that is already set.")
    parser.add_argument("--status", action="store_true",
                        help="Print progress and disagreements, change nothing.")
    args = parser.parse_args()

    path = Path(args.csv)
    rows, fields = load(path)
    index = {(r["case_id"], r["config"]): r for r in rows}

    if args.status or (not args.suggest and not args.decision and not args.note):
        print_status(rows)
        return

    for field in ("ai_suggested_label", "adjudication"):
        if field not in fields:
            raise SystemExit(
                f"{path} has no {field!r} column. Regenerate it with "
                "scripts/analyze_privacy_results.py --review-csv first."
            )

    missing = [f"{c}:{g}" for c, g, _ in args.suggest + args.decision + args.note
               if (c, g) not in index]
    if missing:
        raise SystemExit(f"Not rows in {path.name}: {', '.join(missing)}")

    already = [f"{c}:{g}" for c, g, _ in args.decision
               if (index[(c, g)].get(_MANUAL_LABEL_FIELD) or "").strip()]
    if already and not args.replace:
        raise SystemExit(
            f"These rows already carry a human decision: {', '.join(already)}. "
            "Pass --replace to change them."
        )

    dest = backup(path)
    stamp = datetime.now(UTC).strftime("%Y-%m-%d")
    adjudication = f"{args.source}"
    if args.batch:
        adjudication += f", batch {args.batch}"
    adjudication += f", {stamp}"

    for case_id, config, label in args.suggest:
        index[(case_id, config)]["ai_suggested_label"] = label
    for case_id, config, label in args.decision:
        row = index[(case_id, config)]
        row[_MANUAL_LABEL_FIELD] = label
        row["adjudication"] = adjudication
    for case_id, config, text in args.note:
        index[(case_id, config)]["manual_notes"] = text

    save(path, rows, fields)

    print(f"Backed up to {dest.name}")
    if args.suggest:
        print(f"Recorded {len(args.suggest)} assistant suggestion(s) "
              "(ai_suggested_label; not a human label):")
        for case_id, config, label in args.suggest:
            print(f"  {case_id}/{config} -> {label}")
    if args.decision:
        print(f"Recorded {len(args.decision)} human decision(s) "
              f"(manual_label, stamped {adjudication!r}):")
        for case_id, config, label in args.decision:
            print(f"  {case_id}/{config} -> {label}")
    if args.note:
        print(f"Recorded {len(args.note)} reviewer note(s):")
        for case_id, config, text in args.note:
            print(f"  {case_id}/{config}: {text[:90]}")
    print()
    print_status(rows)


if __name__ == "__main__":
    main()
