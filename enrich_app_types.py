#!/usr/bin/env python3
"""Enrich batch_results.json with top 10 app names for each keyword.

Fetches from iTunes Search API and adds a 'top_10_names' field to each entry.
Saves progress incrementally so it can be resumed if interrupted.
"""

import json
import time
import sys
from itunes_api import search_apps

BATCH_FILE = "batch_results.json"


def main():
    with open(BATCH_FILE) as f:
        results = json.load(f)

    total = len(results)
    enriched = 0
    skipped = 0

    print(f"Enriching {total} keywords with top 10 app names...\n", file=sys.stderr)

    for i, r in enumerate(results):
        kw = r.get("keyword", "")

        # Skip if already enriched or has error
        if r.get("top_10_names") or r.get("error"):
            skipped += 1
            continue

        print(f"[{i+1}/{total}] {kw}...", file=sys.stderr, end=" ", flush=True)

        try:
            apps = search_apps(kw, country="us", limit=10)
            r["top_10_names"] = [a["name"] for a in apps[:10]]
            enriched += 1
            print(f"found {len(r['top_10_names'])} apps", file=sys.stderr)
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            r["top_10_names"] = []

        # Save progress every 25 keywords
        if enriched % 25 == 0 and enriched > 0:
            with open(BATCH_FILE, "w") as f:
                json.dump(results, f, indent=2)
            print(f"  [saved progress: {enriched} enriched]", file=sys.stderr)

        if i < total - 1:
            time.sleep(3)

    # Final save
    with open(BATCH_FILE, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nDone! Enriched {enriched}, skipped {skipped} (already had data or errors).", file=sys.stderr)
    print(f"Results saved to {BATCH_FILE}", file=sys.stderr)


if __name__ == "__main__":
    main()
