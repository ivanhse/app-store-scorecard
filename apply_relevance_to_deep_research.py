#!/usr/bin/env python3
"""Overlay relevance-filtered metrics onto deep_research.json.

The web app reads deep_research.json. Instead of adding a new endpoint, we
rewrite that file in place so the existing UI reflects the relevance fix.

For every keyword:
  - demand_level, concentration_index, avg_rating_count, total_ratings_top10,
    weak_apps_in_top10, mature_apps_pct, avg_star_rating, dominant_category,
    free_count/paid_count, incumbent, top3  → recomputed against RELEVANT
    apps only (intent_relevance >= 0.5 per top-10 app).
  - supply_level derived from relevant avg_rating_count.
  - If intent_relevance < 0.3 we add kill `off_intent` (penalty 0.1), and
    rerun classify + compute_vibe_roi so vibe_roi collapses to ~0.
  - If 0.3 ≤ intent_relevance < 0.5 we add kill `weak_intent` (penalty 0.5).
  - `intent_relevance` and `relevant_count` are added to every row.

Run:
  python3 apply_relevance_to_deep_research.py
"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from deep_research import (
    classify, compute_vibe_roi, normalize_keyword, DOMINANT_INCUMBENTS,
)

DEEP_PATH = os.path.join(ROOT, "deep_research.json")
REL_PATH = os.path.join(ROOT, "relevance_rescored.json")


def supply_from_avg(avg_r: int) -> str:
    if avg_r > 50_000:
        return "VERY HIGH"
    if avg_r > 10_000:
        return "HIGH"
    if avg_r > 3_000:
        return "MODERATE"
    if avg_r > 500:
        return "LOW"
    if avg_r > 0:
        return "VERY LOW"
    return "NONE"


def recompute_incumbent(relevant_apps: list[dict]) -> str | None:
    for a in relevant_apps[:3]:
        name = (a.get("name") or "").lower()
        tokens = set(t for t in re.split(r"[^a-z0-9+]+", name) if t)
        for dom in DOMINANT_INCUMBENTS:
            dom_tokens = dom.split()
            if all(t in tokens for t in dom_tokens):
                return dom
    return None


def main():
    with open(DEEP_PATH) as f:
        deep = json.load(f)
    with open(REL_PATH) as f:
        rel = json.load(f)

    rel_by_norm = {r["keyword_normalized"]: r for r in rel}

    out = []
    missing = 0
    off_intent = 0
    weak_intent = 0

    for row in deep:
        norm = row.get("keyword_normalized")
        r = rel_by_norm.get(norm)
        if not r or "error" in r or r.get("intent_relevance") is None:
            # Keep the old row but flag it
            row["intent_relevance"] = None
            row["relevant_count"] = None
            out.append(row)
            missing += 1
            continue

        intent = r["intent_relevance"]
        relevant_apps = [a for a in r["top10_scored"] if a["relevance"] >= 0.5]
        rel_ratings = [a["rating_count"] for a in relevant_apps]

        # Relevance-filtered aggregates
        total_r = sum(rel_ratings)
        max_r = max(rel_ratings) if rel_ratings else 0
        avg_r = int(total_r / len(relevant_apps)) if relevant_apps else 0
        weak = sum(1 for x in rel_ratings if x < 1000)

        stars = [a["star_rating"] for a in relevant_apps if a["star_rating"] > 0]
        avg_stars = round(sum(stars) / len(stars), 2) if stars else 0

        free = sum(1 for a in relevant_apps if a.get("price", 0) == 0)
        paid = len(relevant_apps) - free

        cats = {}
        for a in relevant_apps:
            c = a.get("category") or ""
            if c:
                cats[c] = cats.get(c, 0) + 1
        dominant_cat = max(cats, key=cats.get) if cats else row.get("dominant_category", "")
        cat_focus = (round(cats[dominant_cat] / len(relevant_apps), 2)
                     if relevant_apps and dominant_cat in cats else 0)

        incumbent = recompute_incumbent(
            sorted(relevant_apps, key=lambda a: -a["rating_count"])
        )

        # Overwrite the visible aggregates
        row["total_ratings_top10"] = total_r
        row["max_rating_count"] = max_r
        row["avg_rating_count"] = avg_r
        row["weak_apps_in_top10"] = weak
        row["avg_star_rating"] = avg_stars
        row["concentration_index"] = r.get("rel_gini") if r.get("rel_gini") is not None else 0
        row["dominant_category"] = dominant_cat
        row["category_focus"] = cat_focus
        row["free_count"] = free
        row["paid_count"] = paid
        row["demand_level"] = r["demand_rel_label"]
        row["supply_level"] = supply_from_avg(avg_r)
        row["incumbent"] = incumbent
        row["intent_relevance"] = intent
        row["relevant_count"] = len(relevant_apps)

        # Top-3 / top-10 lists reflect relevant apps first, then fillers
        sorted_relevant = sorted(relevant_apps, key=lambda a: -a["rating_count"])
        row["top3"] = [
            {"name": a["name"], "rating_count": a["rating_count"],
             "star_rating": a["star_rating"], "price": a.get("price", 0),
             "developer": a.get("developer", ""), "category": a.get("category", "")}
            for a in sorted_relevant[:3]
        ]
        row["top10_names"] = [a["name"] for a in sorted(
            r["top10_scored"], key=lambda a: (-a["relevance"], -a["rating_count"]))]

        # Re-run classify + vibe_roi with the relevance-aware signals
        kills, wins, reasons, penalty, boost = classify(norm, row)

        if intent < 0.30:
            kills = list(kills) + ["off_intent"]
            penalty *= 0.10
            reasons = list(reasons) + [f"kill:off_intent(rel={intent})"]
            off_intent += 1
        elif intent < 0.50:
            kills = list(kills) + ["weak_intent"]
            penalty *= 0.50
            reasons = list(reasons) + [f"kill:weak_intent(rel={intent})"]
            weak_intent += 1

        roi = compute_vibe_roi(norm, row, kills, wins, penalty, boost)

        row["kills"] = kills
        row["wins"] = wins
        row["reasons"] = reasons
        row.update(roi)

        out.append(row)

    out.sort(key=lambda r: r.get("vibe_roi", -1), reverse=True)

    with open(DEEP_PATH, "w") as f:
        json.dump(out, f, indent=2)

    print(f"Updated {len(out)} rows (missing={missing}, off_intent={off_intent}, weak_intent={weak_intent})")

    # Sanity checks
    print("\nSpot checks:")
    for kw in ("jury duty tracker", "vitamin tracker", "baby food tracker",
               "airline seat picker", "flood alert", "cpap tracker"):
        for r in out:
            if r.get("keyword_normalized") == kw:
                print(f"  {kw:30} vibe_roi={r.get('vibe_roi','?'):>6}  "
                      f"demand={r.get('demand_level','?'):<10}  "
                      f"gini={r.get('concentration_index','?'):<5}  "
                      f"intent_rel={r.get('intent_relevance'):<4}  "
                      f"kills={r.get('kills', [])}")
                break

    print("\nTop 15 by vibe_roi (post-relevance):")
    for r in out[:15]:
        print(f"  {r.get('vibe_roi',0):>6.2f}  rel={r.get('intent_relevance','?'):<4}  "
              f"demand={r.get('demand_level','?'):<10}  {r['keyword_normalized']}")


if __name__ == "__main__":
    main()
