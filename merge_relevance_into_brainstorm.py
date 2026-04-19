#!/usr/bin/env python3
"""Merge relevance-aware signals from relevance_rescored.json into
batch_results.json rows used by the Brainstorm tab.

Adds per-row:
  - intent_relevance                (0..1 share of top-10 that matches intent)
  - demand_rel_label                (relevance-aware demand bucket)
  - rel_total_ratings               (sum of ratings among relevant apps only)
  - ease_of_entry                   ({"label", "reason", "top_relevant_rating", "weak_relevant_pct"})
  - verdict_intent                  (OFF-INTENT / GREAT / AVOID / …)
  - relevant_count                  (# of apps in top-10 that passed rel>=0.5)

Run:
  python3 merge_relevance_into_brainstorm.py
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from relevance_rescore import normalize_keyword

BATCH = os.path.join(ROOT, "batch_results.json")
REL = os.path.join(ROOT, "relevance_rescored.json")


def main():
    with open(BATCH) as f:
        batch = json.load(f)
    with open(REL) as f:
        rel = json.load(f)

    by_norm = {r.get("keyword_normalized"): r for r in rel}

    hit, miss = 0, 0
    for row in batch:
        kw = row.get("keyword")
        if not kw:
            continue
        rr = by_norm.get(normalize_keyword(kw))
        if not rr:
            miss += 1
            continue
        hit += 1
        row["intent_relevance"] = rr.get("intent_relevance")
        row["relevant_count"] = rr.get("relevant_count")
        row["rel_total_ratings"] = rr.get("rel_total_ratings")
        row["demand_rel_label"] = rr.get("demand_rel_label")
        row["ease_of_entry"] = rr.get("ease_of_entry")
        row["verdict_intent"] = rr.get("verdict")

    with open(BATCH, "w") as f:
        json.dump(batch, f, indent=2)

    print(f"Merged relevance into {hit} rows, missing {miss}. "
          f"Wrote {len(batch)} → batch_results.json")


if __name__ == "__main__":
    main()
