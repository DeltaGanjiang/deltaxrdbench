"""Command-line interface for XRDBench."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .benchmark import evaluate

def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate an XRD model submission")
    parser.add_argument("dataset", help="Dataset manifest in JSONL format")
    parser.add_argument("submission", help="Model submission in JSONL format")
    parser.add_argument("--data-root", help="Directory used to resolve pattern paths")
    parser.add_argument("--output", help="Write the complete JSON report to this path")
    args = parser.parse_args()
    rendered = json.dumps(evaluate(args.dataset, args.submission, data_root=args.data_root).to_dict(), ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)

if __name__ == "__main__":
    main()
