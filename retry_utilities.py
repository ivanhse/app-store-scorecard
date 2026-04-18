#!/usr/bin/env python3
"""Retry keywords in batch_results.json that errored (429/403 from iTunes).

Uses longer sleeps + exponential backoff. Safe to run repeatedly.
"""

import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import requests
from itunes_api import analyze_competition, search_apps as _search
from batch_evaluate import score_opportunity


BATCH = os.path.join(ROOT, "batch_results.json")


def fetch_with_backoff(kw: str) -> list[dict]:
    """Mirror itunes_api.search_apps but with retries."""
    for attempt in range(6):
        try:
            return _search(kw, country="us", limit=10)
        except requests.HTTPError as e:
            code = getattr(e.response, "status_code", None)
            wait = 10 * (attempt + 1)
            print(f"    HTTP {code}; sleep {wait}s then retry {attempt+2}/6", flush=True)
            time.sleep(wait)
        except Exception as e:
            wait = 5 * (attempt + 1)
            print(f"    {type(e).__name__}: {e}; sleep {wait}s", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"exhausted retries for {kw}")


def main():
    with open(BATCH) as f:
        data = json.load(f)

    errs = [(i, r) for i, r in enumerate(data) if "error" in r]
    print(f"Retrying {len(errs)} errored rows…", flush=True)

    fixed = 0
    for n, (idx, row) in enumerate(errs, 1):
        kw = row["keyword"]
        try:
            apps = fetch_with_backoff(kw)
            analysis = analyze_competition(apps)
            sc = score_opportunity(analysis)
            data[idx] = {
                "keyword": kw,
                "score": sc,
                "opportunity": analysis.get("opportunity", "?"),
                "demand_level": analysis.get("demand_level", "?"),
                "supply_level": analysis.get("supply_level", "?"),
                "total_ratings_top10": analysis.get("total_ratings_top10", 0),
                "avg_rating_count": analysis.get("avg_rating_count", 0),
                "avg_star_rating": analysis.get("avg_star_rating", 0),
                "stale_apps": analysis.get("stale_apps", 0),
                "low_rated_apps": analysis.get("low_rated_apps", 0),
                "weak_apps_in_top10": analysis.get("weak_apps_in_top10", 0),
                "mature_apps_pct": analysis.get("mature_apps_pct"),
                "concentration_index": analysis.get("concentration_index"),
                "top_3_apps": [
                    {"name": a["name"], "ratings": a["rating_count"], "stars": a["star_rating"]}
                    for a in apps[:3]
                ],
                "top_10_names": [a["name"] for a in apps[:10]],
            }
            fixed += 1
            print(f"[{n}/{len(errs)}] {kw} → score={sc} {analysis.get('opportunity','?')}", flush=True)
        except Exception as e:
            print(f"[{n}/{len(errs)}] STILL FAILED {kw}: {e}", flush=True)
        # Generous pause to stay under iTunes throttle.
        time.sleep(2.5)

        # Incremental save every 10
        if n % 10 == 0:
            data.sort(key=lambda r: r.get("score", 0), reverse=True)
            with open(BATCH, "w") as f:
                json.dump(data, f, indent=2)

    data.sort(key=lambda r: r.get("score", 0), reverse=True)
    with open(BATCH, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\nFixed {fixed}/{len(errs)} rows.", flush=True)


if __name__ == "__main__":
    main()
