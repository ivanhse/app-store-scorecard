#!/usr/bin/env python3
"""Retry any deep_research.json rows that have `error` set.

For each errored keyword:
  1. Re-fetch iTunes top-25 with slow backoff.
  2. Run the full `enrich` + `classify` + `compute_vibe_roi` locally.
  3. Also run `relevance_rescore.evaluate` against the same top-10 and update
     relevance_rescored.json.
  4. Save updated deep_research.json and relevance_rescored.json.

Run `apply_relevance_to_deep_research.py` + `build_clusters.py` afterwards.
"""

import json
import os
import sys
import time

import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from deep_research import enrich, classify, compute_vibe_roi, normalize_keyword
from relevance_rescore import (
    evaluate as relevance_evaluate,
    capture_top10,
    normalize_keyword as rel_normalize,
)

ITUNES = "https://itunes.apple.com/search"
DEEP = os.path.join(ROOT, "deep_research.json")
REL = os.path.join(ROOT, "relevance_rescored.json")
DEEP_CACHE = os.path.join(ROOT, "deep_research_cache.json")
REL_CACHE = os.path.join(ROOT, "relevance_cache.json")


def fetch(kw: str, limit: int = 25) -> list[dict]:
    for attempt in range(8):
        try:
            r = requests.get(
                ITUNES,
                params={"term": kw, "entity": "software", "country": "us", "limit": limit},
                timeout=20,
            )
            if r.status_code in (403, 429):
                wait = 15 * (attempt + 1)
                print(f"    HTTP {r.status_code}; sleep {wait}s (retry {attempt+2}/8)", flush=True)
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json().get("results", [])
        except requests.HTTPError:
            wait = 15 * (attempt + 1)
            print(f"    HTTPError; sleep {wait}s", flush=True)
            time.sleep(wait)
        except Exception as e:
            wait = 5 * (attempt + 1)
            print(f"    {type(e).__name__}; sleep {wait}s", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"exhausted retries for {kw}")


def main():
    with open(DEEP) as f:
        deep = json.load(f)
    with open(REL) as f:
        rel = json.load(f)

    # caches
    deep_cache = {}
    if os.path.exists(DEEP_CACHE):
        with open(DEEP_CACHE) as f:
            deep_cache = json.load(f)
    rel_cache = {}
    if os.path.exists(REL_CACHE):
        with open(REL_CACHE) as f:
            rel_cache = json.load(f)

    deep_by_norm = {r.get("keyword_normalized"): i for i, r in enumerate(deep)}
    rel_by_norm = {r.get("keyword_normalized"): i for i, r in enumerate(rel)}

    err_kws = [r["keyword_normalized"] for r in deep if "error" in r]
    print(f"Retrying {len(err_kws)} errored keywords...", flush=True)

    for n, normed in enumerate(err_kws, 1):
        try:
            raw = fetch(normed)
            # --- deep_research row ---
            signals = enrich(normed, raw) or {}
            kills, wins, reasons, penalty, boost = classify(normed, signals)
            roi = compute_vibe_roi(normed, signals, kills, wins, penalty, boost)
            new_row = {
                "keyword_original": deep[deep_by_norm[normed]].get("keyword_original", normed),
                "keyword_normalized": normed,
                **signals,
                "kills": kills,
                "wins": wins,
                "reasons": reasons,
                **roi,
            }
            deep[deep_by_norm[normed]] = new_row
            deep_cache[normed] = signals

            # --- relevance row ---
            top10 = capture_top10(raw)
            rel_cache[normed] = {"top10": top10}
            rel_row = relevance_evaluate(normed, top10)
            if normed in rel_by_norm:
                rel[rel_by_norm[normed]] = rel_row
            else:
                rel.append(rel_row)

            print(f"[{n}/{len(err_kws)}] {normed} → vibe_roi={roi.get('vibe_roi','?')} "
                  f"demand={signals.get('demand_level','?')} "
                  f"intent={rel_row.get('intent_relevance')}", flush=True)
        except Exception as e:
            print(f"[{n}/{len(err_kws)}] FAILED {normed}: {e}", flush=True)

        time.sleep(3)

    with open(DEEP, "w") as f:
        json.dump(deep, f, indent=2)
    with open(REL, "w") as f:
        json.dump(rel, f, indent=2)
    with open(DEEP_CACHE, "w") as f:
        json.dump(deep_cache, f)
    with open(REL_CACHE, "w") as f:
        json.dump(rel_cache, f)

    still = sum(1 for r in deep if "error" in r)
    print(f"\nSaved. deep_research.json errors remaining: {still}", flush=True)


if __name__ == "__main__":
    main()
