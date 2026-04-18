#!/usr/bin/env python3
"""Comprehensive "all utilities" keyword pack.

Run:
  python3 utilities_ext.py            # extend batch_results.json with new kws
  (then run deep_research.py, relevance_rescore.py, apply_relevance_to_deep_research.py, build_clusters.py)
"""

import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from itunes_api import search_apps, analyze_competition
from batch_evaluate import score_opportunity, KEYWORDS as KW1
from batch_evaluate_2 import KEYWORDS as KW2


UTILITIES = [
    # --- Phone / device maintenance ---
    "speaker cleaner", "water eject phone", "phone speaker cleaner",
    "dust cleaner phone", "charge port cleaner", "phone screen cleaner",
    "earbuds cleaner", "phone cooler app", "phone heat alert",
    "dead pixel fixer", "screen burn in test", "display color test",
    "refresh rate tester", "battery capacity tester", "charging speed tester",
    "microphone tester app", "proximity sensor test", "touchscreen test",
    "vibration motor test", "haptic tester app",

    # --- Sound tools ---
    "decibel meter app", "sound level meter", "tone generator app",
    "frequency generator app", "hearing test app", "tinnitus tone app",
    "brown noise generator", "pink noise generator", "binaural beats app",
    "rain sound generator", "fan sound generator", "ocean wave sounds",
    "spectrum analyzer app", "audio level meter", "chromatic tuner",

    # --- Photo / camera utilities ---
    "light meter photo", "exposure calculator app", "color picker camera",
    "exif viewer app", "photo metadata viewer", "watermark photo app",
    "photo date stamp", "background remover photo", "image upscaler ai",
    "photo enhancer ai", "photo compressor app", "heic to jpg converter",
    "webp to jpg converter", "gif maker app", "live photo to video",

    # --- File / format utilities ---
    "pdf compressor app", "video compressor app", "audio extractor mp3",
    "video to gif converter", "voice memo transcriber", "audio joiner app",
    "pdf merger app", "zip extractor app", "rar extractor app",
    "m4a to mp3 converter",

    # --- Network / connectivity ---
    "wifi analyzer app", "wifi signal strength", "internet speed test app",
    "ping tester app", "wifi password share", "hotspot monitor app",
    "bluetooth signal meter", "lan scanner app", "router login helper",
    "network monitor app",

    # --- Security / privacy ---
    "password vault app", "secret photo vault", "2fa authenticator app",
    "fake call maker", "call blocker app", "spam text blocker",
    "private browser app", "incognito browser app", "app lock privacy",
    "hidden notes app",

    # --- Measurement tools ---
    "ar tape measure", "ar ruler app", "ar height measure",
    "bubble level app", "protractor app", "plumb bob app",
    "lux light meter", "compass app pro", "altimeter app",
    "magnetometer app", "angle finder app", "spirit level app",
    "distance meter ar", "room scanner 3d", "floor plan scanner",

    # --- Random / decision ---
    "dice roller app", "coin flip app", "spinner wheel app",
    "name picker random", "yes no decision", "magic 8 ball",
    "bingo number generator", "raffle drawer app", "lottery number generator",
    "random picker app",

    # --- Keyboard / input / text ---
    "custom fonts keyboard", "sticker maker app", "emoji maker app",
    "handwriting to text", "voice to text app", "ocr text scanner",
    "translator camera app", "offline translator app",

    # --- AR / scanning / object ID ---
    "nutrition label scanner", "wine label scanner", "medicine barcode scanner",
    "plant identifier ai", "bug identifier app", "mushroom identifier app",
    "bird identifier ai", "fish identifier ai",

    # --- Phone cleanup / storage ---
    "duplicate photo cleaner", "duplicate contact cleaner", "storage analyzer app",
    "big file finder", "screenshot cleaner", "contact merger app",
    "photo album organizer", "burst photo picker",

    # --- Clock / time ---
    "world clock widget", "countdown widget app", "digital clock widget",
    "stopwatch lap app", "interval timer workout",

    # --- Misc / novelty ---
    "flashlight strobe app", "mirror app real", "magnifier loupe app",
    "whistle finder app", "voice changer app",
]


BATCH_RESULTS = os.path.join(ROOT, "batch_results.json")


def process_new():
    with open(BATCH_RESULTS) as f:
        existing = json.load(f)

    existing_kws = {r["keyword"].lower() for r in existing}
    new_kws = [k for k in UTILITIES if k.lower() not in existing_kws]
    print(f"Existing: {len(existing)} keywords. New utilities to process: {len(new_kws)}")

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
            print(f"[{i}/{len(new_kws)}] {kw} → score={sc} {analysis.get('opportunity','?')}")
            out_rows.append(row)
        except Exception as e:
            print(f"[{i}/{len(new_kws)}] ERROR {kw}: {e}")
            out_rows.append({"keyword": kw, "score": 0, "error": str(e)})
        time.sleep(0.5)

    merged = existing + out_rows
    merged.sort(key=lambda r: r.get("score", 0), reverse=True)

    with open(BATCH_RESULTS, "w") as f:
        json.dump(merged, f, indent=2)

    print(f"\nWrote {len(merged)} rows to batch_results.json "
          f"({len(out_rows)} new, {len(existing)} kept)")


if __name__ == "__main__":
    process_new()
