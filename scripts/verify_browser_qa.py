#!/usr/bin/env python3
"""Read-only verification of an existing browser_qa_harness.mjs evidence file."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'agent-publisher'))
from agents.browser_qa import evaluate_browser_qa  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    parser.add_argument('--output', type=Path, help='optional evaluated receipt, never changes QA task state')
    args = parser.parse_args(argv)
    evidence = json.loads(args.evidence.read_text(encoding='utf-8'))
    result = evaluate_browser_qa(evidence, evidence_dir=args.evidence.parent)
    serialized = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.write_text(serialized, encoding='utf-8')
    print(serialized)
    return 0 if not result['incomplete_scopes'] else 2


if __name__ == '__main__':
    sys.exit(main())
