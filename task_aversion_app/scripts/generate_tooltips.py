"""
Semi-automated tooltip generator.

Usage examples:
  python scripts/generate_tooltips.py --elements tutorial_button,dashboard_header
  python scripts/generate_tooltips.py --elements-from data/elements.txt

By default this script generates lightweight, deterministic variations without
calling an API. If you set OPENAI_API_KEY and have the `openai` package
installed, it will attempt to use the Chat Completions API to propose richer
variants. All output is written to data/tooltips_raw.json for manual review.
"""

import argparse
import json
import os
import random
from pathlib import Path
from typing import List, Dict

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RAW_FILE = DATA_DIR / "tooltips_raw.json"


def load_existing() -> Dict[str, List[str]]:
    if RAW_FILE.exists():
        with open(RAW_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save(data: Dict[str, List[str]]):
    with open(RAW_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"wrote {RAW_FILE}")


def simple_variations(text: str, n: int = 10) -> List[str]:
    prefixes = [
        "Tip:", "Hint:", "Heads up:", "FYI:", "Quick note:", "Try this:",
        "Remember:", "Good to know:", "Pro move:", "Pro tip:"
    ]
    suffixes = [
        "", "—fastest path", "—takes seconds", "to get started", "right here",
        "when you need it", "in a pinch", "and keep moving", "for clarity", "for context"
    ]
    variants = set()
    while len(variants) < n:
        pre = random.choice(prefixes)
        suf = random.choice(suffixes)
        variants.add(f"{pre} {text} {suf}".strip())
    return list(variants)


def maybe_openai_variations(base: str, n: int) -> List[str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return []
    try:
        import openai  # type: ignore

        client = openai.OpenAI(api_key=api_key)
        prompt = f"Generate {n} concise, friendly tooltips (max 100 chars) that describe: {base}"
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            n=1,
        )
        text = resp.choices[0].message.content or ""
        lines = [ln.strip("-• ").strip() for ln in text.splitlines() if ln.strip()]
        return [ln for ln in lines if ln]
    except Exception as exc:  # pragma: no cover
        print("OpenAI generation failed, falling back to local variations:", exc)
        return []


def generate_for_key(key: str, base_text: str, total: int = 10) -> List[str]:
    results = maybe_openai_variations(base_text, total)
    if len(results) < total:
        results.extend(simple_variations(base_text, total - len(results)))
    # Deduplicate and truncate
    uniq = []
    for item in results:
        if item not in uniq:
            uniq.append(item)
    return uniq[:total]


def main():
    parser = argparse.ArgumentParser(description="Generate tooltip variations.")
    parser.add_argument("--elements", type=str, default="", help="Comma-separated element ids")
    parser.add_argument("--elements-from", type=str, help="Path to file with one element per line")
    parser.add_argument("--base-text", type=str, default="Click to learn more about this feature.")
    parser.add_argument("--count", type=int, default=10, help="Variations per element")
    args = parser.parse_args()

    elements: List[str] = []
    if args.elements:
        elements.extend([e.strip() for e in args.elements.split(",") if e.strip()])
    if args.elements_from:
        with open(args.elements_from, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    elements.append(line)

    if not elements:
        print("No elements provided. Use --elements or --elements-from.")
        return

    data = load_existing()
    for el in elements:
        print(f"Generating tooltips for '{el}' ...")
        data[el] = generate_for_key(el, args.base_text, total=args.count)

    save(data)


if __name__ == "__main__":
    main()

