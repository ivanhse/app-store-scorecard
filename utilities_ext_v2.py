#!/usr/bin/env python3
"""Utilities pack v2 — fills gaps found in v1 coverage audit.

Covers: AI voice/audio, AI document, Photo ID / passport,
anti-stalking tracker detectors, display/pixel tests, body sensor tests,
plus a few under-represented misc groups.

Run:
  python3 utilities_ext_v2.py        # append new kws to batch_results.json
  (then run run_full_pipeline.sh)
"""

import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from itunes_api import search_apps, analyze_competition
from batch_evaluate import score_opportunity


UTILITIES_V2 = [
    # --- AI voice / audio ---
    "ai voice cleaner", "ai audio cleaner", "ai voice clone app",
    "ai dictation app", "ai subtitle generator", "ai transcription app",
    "voice isolation app", "audio noise remover",

    # --- AI document ---
    "ai pdf summarizer", "ai document reader", "ai contract reader",
    "ai book summarizer", "ai read aloud app", "ai pdf translator",
    "ai research assistant", "ai email writer",

    # --- Photo ID / passport ---
    "passport photo maker", "visa photo app", "id photo maker",
    "linkedin headshot app", "ai headshot generator", "resume photo maker",

    # --- Anti-stalking / tracker detect ---
    "airtag scanner app", "hidden tracker detector", "anti stalking app",
    "bluetooth tracker finder", "nfc tag reader", "tile tracker scanner",

    # --- Display / pixel tests ---
    "pixel test app", "screen test utility", "oled burn in test",
    "monitor color test", "screen flicker test",

    # --- Body sensor tests ---
    "hearing test frequency", "vision test eye chart", "color blindness test",
    "reaction time test", "lung capacity test",

    # --- Novelty / fortune ---
    "crystal ball app", "ouija board app", "magic 8 ball app",

    # --- Smart home remotes ---
    "tv remote universal", "ac remote universal", "projector remote app",

    # --- Keyboard / input ---
    "ascii art keyboard", "emoji keyboard cool", "math keyboard app",

    # --- Misc callouts ---
    "world clock widget", "speed camera detector",
]


BATCH_RESULTS = os.path.join(ROOT, "batch_results.json")


def process_new():
    with open(BATCH_RESULTS) as f:
        existing = json.load(f)

    existing_kws = {r["keyword"].lower() for r in existing}
    new_kws = [k for k in UTILITIES_V2 if k.lower() not in existing_kws]
    print(f"Existing: {len(existing)} keywords. New v2 utilities to process: {len(new_kws)}")

    out_rows = []
    for i, kw in enumerate(new_kws, 1):
        try:
            apps = search_apps(kw, country="us", limit=10)
            analysis = analyze_competition(apps)
            sc = score_opportunity(analysis)
            row = {
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
            print(f"[{i}/{len(new_kws)}] {kw} → score={sc} {analysis.get('opportunity','?')}", flush=True)
            out_rows.append(row)
        except Exception as e:
            print(f"[{i}/{len(new_kws)}] ERROR {kw}: {e}", flush=True)
            out_rows.append({"keyword": kw, "score": 0, "error": str(e)})
        time.sleep(1.2)

    merged = existing + out_rows
    merged.sort(key=lambda r: r.get("score", 0), reverse=True)

    with open(BATCH_RESULTS, "w") as f:
        json.dump(merged, f, indent=2)

    print(f"\nWrote {len(merged)} rows to batch_results.json "
          f"({len(out_rows)} new, {len(existing)} kept)", flush=True)


if __name__ == "__main__":
    process_new()
