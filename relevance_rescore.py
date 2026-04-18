#!/usr/bin/env python3
"""Relevance-aware rescoring for all 1000 keywords.

Key idea: a keyword like "jury duty tracker" pulls up USCIS case trackers and
generic hours-trackers. Those apps inflate demand/concentration metrics while
being completely off-intent. We re-score top-10 by *keyword relevance* and
recompute every aggregate metric using ONLY the apps that match the intent.

Output:
  - relevance_cache.json  — full top10 raw signals per normalized keyword
  - relevance_rescored.json — per-keyword: relevant_count, demand_rel, gini_rel,
    ease_of_entry, verdict

Run:
  python3 relevance_rescore.py
"""

import json
import os
import re
import sys
import time
from datetime import datetime

import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from batch_evaluate import KEYWORDS as KW1
from batch_evaluate_2 import KEYWORDS as KW2
try:
    from utilities_ext import UTILITIES as KW3
except ImportError:
    KW3 = []
try:
    from utilities_ext_v2 import UTILITIES_V2 as KW4
except ImportError:
    KW4 = []

ITUNES = "https://itunes.apple.com/search"
NOW = datetime.now()

CACHE_PATH = os.path.join(ROOT, "relevance_cache.json")
OUT_PATH = os.path.join(ROOT, "relevance_rescored.json")

# Tokens that describe app *type*, not subject. Stripping these leaves domain tokens.
GENERIC_TOKENS = {
    "app", "apps", "tracker", "trackers", "tracking", "tracks",
    "logger", "log", "logs", "logging",
    "diary", "diaries", "journal", "journals", "journaling",
    "reminder", "reminders", "alert", "alerts",
    "calc", "calculator", "calculators", "converter", "converters", "conversion",
    "scanner", "scanners", "finder", "finders",
    "generator", "generators", "planner", "planners",
    "guide", "guides", "manual", "manuals", "handbook",
    "pro", "plus", "lite", "free", "paid", "premium", "basic",
    "simple", "easy", "quick", "smart", "best", "ultimate",
    "tool", "tools", "utility", "utilities", "helper", "helpers",
    "manager", "managers", "organizer", "organizers",
    "monitor", "monitors", "watcher", "checker", "checkers",
    "counter", "counters", "timer", "timers", "stopwatch",
    "maker", "makers", "builder", "builders", "creator", "creators",
    "record", "records", "recording", "record",
    "test", "tests", "tester",
    "chart", "charts", "map", "maps",
    "my", "the", "a", "an", "for", "of", "and", "or", "to", "in", "on",
    "ios", "iphone", "ipad", "mobile",
    "list", "lists", "listing",
    "daily", "weekly", "monthly", "yearly",  # frequency modifiers — not domain
    "widget", "widgets",
    "new", "old",
    "i",
}

# Intent-bearing generic tokens: these *might* matter for matching (e.g. "workout", "exercise")
# but we treat them as soft-domain, not hard. Currently empty — keeping pure split.


def normalize_keyword(kw: str) -> str:
    kw = kw.lower().strip()
    for suf in [" apps", " app"]:
        if kw.endswith(suf):
            kw = kw[: -len(suf)].strip()
    return kw


WORD_RE = re.compile(r"[^a-z0-9+]+")


def tokenize(text: str) -> list[str]:
    text = (text or "").lower()
    return [t for t in WORD_RE.split(text) if t]


def stem_lite(tok: str) -> str:
    """Very light stemming so 'exercises' ~ 'exercise', 'tracking' ~ 'track'."""
    if len(tok) <= 4:
        return tok
    for suf in ("ings", "ing", "ers", "er", "ies", "ied", "es", "s", "ed"):
        if tok.endswith(suf) and len(tok) - len(suf) >= 4:
            return tok[: -len(suf)]
    return tok


def domain_tokens(keyword: str) -> list[str]:
    toks = tokenize(keyword)
    stemmed = [stem_lite(t) for t in toks]
    # keep only tokens whose surface form isn't in the generic list
    domain = []
    for raw, stem in zip(toks, stemmed):
        if raw in GENERIC_TOKENS:
            continue
        if stem in GENERIC_TOKENS:
            continue
        # skip pure numbers
        if raw.isdigit():
            continue
        domain.append(stem)
    return domain


def app_relevance(app_name: str, app_category: str, d_tokens: list[str]) -> float:
    """Return 0..1 score. 1.0 = strong match on domain tokens in the name."""
    if not d_tokens:
        return 0.5  # no domain tokens to match → neutral

    name_toks = {stem_lite(t) for t in tokenize(app_name)}
    # Count domain tokens that appear (exact or stem) in the app name
    hits = 0
    for dt in d_tokens:
        if dt in name_toks:
            hits += 1
            continue
        # soft: prefix match if len >= 5
        if len(dt) >= 5:
            if any(nt.startswith(dt[:5]) or dt.startswith(nt[:5]) and len(nt) >= 5 for nt in name_toks):
                hits += 0.5

    score = hits / len(d_tokens)
    return min(1.0, score)


def search_apps(keyword: str, country: str = "us", limit: int = 25, retries: int = 5):
    last_err = None
    for attempt in range(retries):
        try:
            r = requests.get(
                ITUNES,
                params={"term": keyword, "entity": "software",
                        "country": country, "limit": limit},
                timeout=20,
            )
            if r.status_code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json().get("results", [])
        except Exception as e:
            last_err = e
            time.sleep(3 * (attempt + 1))
    raise last_err


def capture_top10(raw_results: list[dict]) -> list[dict]:
    out = []
    for r in raw_results[:10]:
        released = r.get("releaseDate", "")
        updated = r.get("currentVersionReleaseDate", "")
        out.append({
            "name": r.get("trackName", "") or "",
            "developer": r.get("artistName", "") or "",
            "rating_count": int(r.get("userRatingCount", 0) or 0),
            "star_rating": round(float(r.get("averageUserRating", 0) or 0), 2),
            "price": float(r.get("price", 0) or 0),
            "released": (released or "")[:10],
            "last_updated": (updated or "")[:10],
            "category": r.get("primaryGenreName", "") or "",
            "bundle_id": r.get("bundleId", "") or "",
        })
    return out


def gini(values: list[float]) -> float:
    vals = sorted(v for v in values if v is not None)
    n = len(vals)
    s = sum(vals)
    if n == 0 or s == 0:
        return 0.0
    cum = sum((2 * (i + 1) - n - 1) * v for i, v in enumerate(vals))
    return round(cum / (n * s), 3)


def demand_label(total_ratings: int) -> str:
    if total_ratings > 300_000:
        return "VERY HIGH"
    if total_ratings > 60_000:
        return "HIGH"
    if total_ratings > 15_000:
        return "MODERATE"
    if total_ratings > 3_000:
        return "LOW"
    if total_ratings > 0:
        return "VERY LOW"
    return "NONE"


def ease_of_entry(relevant: list[dict], intent_relevance: float) -> dict:
    """Estimate how hard it is to break in, based on relevant competitors only."""
    n = len(relevant)
    if intent_relevance < 0.30 or n == 0:
        return {
            "label": "UNPROVEN — search intent unclear",
            "reason": "top-10 is mostly off-intent generic apps; no evidence of real demand",
            "top_relevant_rating": 0,
            "weak_relevant_pct": 0.0,
        }
    ratings = [a["rating_count"] for a in relevant]
    top_r = max(ratings) if ratings else 0
    weak = sum(1 for x in ratings if x < 1000)
    weak_pct = weak / n

    if n < 3:
        label = "OPEN — few real competitors, demand unproven"
        reason = f"only {n} of 10 top results match the intent"
    elif top_r < 5_000 and weak_pct >= 0.5:
        label = "EASY — all relevant competitors are small"
        reason = f"strongest relevant app has {top_r:,} ratings, {weak} are weak"
    elif top_r < 30_000:
        label = "MODERATE — mid-size incumbents, room to niche down"
        reason = f"top relevant app has {top_r:,} ratings"
    elif top_r < 150_000:
        label = "HARD — established leader(s)"
        reason = f"top relevant app has {top_r:,} ratings"
    else:
        label = "VERY HARD — entrenched incumbent"
        reason = f"top relevant app has {top_r:,} ratings"

    return {
        "label": label,
        "reason": reason,
        "top_relevant_rating": top_r,
        "weak_relevant_pct": round(weak_pct, 2),
    }


def verdict(intent_relevance: float, relevant: list[dict], demand_rel: str,
            ease: dict) -> str:
    if intent_relevance < 0.30:
        return "OFF-INTENT — App Store returns generic apps; real demand unclear"
    n = len(relevant)
    top_r = ease["top_relevant_rating"]
    if demand_rel in ("VERY LOW", "NONE"):
        return "THIN — real demand too small to sustain a paid app"
    if ease["label"].startswith("EASY"):
        if demand_rel in ("HIGH", "VERY HIGH"):
            return "GREAT — real demand with weak competition"
        return "GOOD — weak competition, modest demand"
    if ease["label"].startswith("MODERATE"):
        if demand_rel in ("HIGH", "VERY HIGH"):
            return "COMPETITIVE — differentiate to win"
        return "NICHE — small but contestable"
    if ease["label"].startswith("HARD"):
        return "HARD — incumbents will out-spend you"
    if ease["label"].startswith("VERY HARD"):
        return "AVOID — entrenched leader"
    if ease["label"].startswith("OPEN"):
        return "UNPROVEN — few relevant apps, validate demand first"
    return "UNCERTAIN"


def evaluate(keyword: str, top10: list[dict]) -> dict:
    normed = normalize_keyword(keyword)
    d_toks = domain_tokens(normed)

    # Per-app relevance
    scored = []
    for a in top10:
        rel = app_relevance(a["name"], a.get("category", ""), d_toks)
        scored.append({**a, "relevance": round(rel, 2)})

    REL_THRESHOLD = 0.5  # at least half the domain tokens must be found
    relevant = [a for a in scored if a["relevance"] >= REL_THRESHOLD]

    # Aggregates on *all* top10 (kept for comparison with old scoring)
    all_total = sum(a["rating_count"] for a in scored)
    all_gini = gini([a["rating_count"] for a in scored])

    # Aggregates on *relevant* apps only
    rel_ratings = [a["rating_count"] for a in relevant]
    rel_total = sum(rel_ratings)
    rel_avg = int(rel_total / len(relevant)) if relevant else 0
    rel_max = max(rel_ratings) if rel_ratings else 0
    rel_gini = gini(rel_ratings) if len(rel_ratings) >= 2 else None

    stars = [a["star_rating"] for a in relevant if a["star_rating"] > 0]
    rel_avg_stars = round(sum(stars) / len(stars), 2) if stars else 0

    # Stale / mature of relevant set
    stale = mature = have_date = 0
    for a in relevant:
        try:
            upd = datetime.strptime(a["last_updated"], "%Y-%m-%d")
            if (NOW - upd).days > 365:
                stale += 1
        except ValueError:
            pass
        try:
            rel_d = datetime.strptime(a["released"], "%Y-%m-%d")
            have_date += 1
            if (NOW - rel_d).days > 3 * 365:
                mature += 1
        except ValueError:
            pass
    mature_pct = round(mature / have_date * 100) if have_date else 0

    # Dominant category of relevant set
    cats = {}
    for a in relevant:
        c = a.get("category") or ""
        if c:
            cats[c] = cats.get(c, 0) + 1
    dominant_cat = max(cats, key=cats.get) if cats else ""

    # Free/paid mix of relevant
    free = sum(1 for a in relevant if a["price"] == 0)
    paid = len(relevant) - free

    intent_relevance = round(len(relevant) / 10, 2)
    demand_rel = demand_label(rel_total)
    demand_all = demand_label(all_total)

    ease = ease_of_entry(relevant, intent_relevance)
    v = verdict(intent_relevance, relevant, demand_rel, ease)

    return {
        "keyword_original": keyword,
        "keyword_normalized": normed,
        "domain_tokens": d_toks,
        "intent_relevance": intent_relevance,
        "relevant_count": len(relevant),

        # Old-style metrics (all top10 — these are the inflated ones)
        "all_total_ratings": all_total,
        "all_gini": all_gini,
        "all_demand_label": demand_all,

        # Relevance-aware metrics
        "rel_total_ratings": rel_total,
        "rel_avg_rating_count": rel_avg,
        "rel_max_rating_count": rel_max,
        "rel_gini": rel_gini,
        "rel_avg_stars": rel_avg_stars,
        "rel_stale_apps": stale,
        "rel_mature_pct": mature_pct,
        "rel_dominant_category": dominant_cat,
        "rel_free_count": free,
        "rel_paid_count": paid,
        "demand_rel_label": demand_rel,

        "ease_of_entry": ease,
        "verdict": v,

        "top10_scored": scored,
        "top_relevant": [
            {"name": a["name"], "rating_count": a["rating_count"],
             "star_rating": a["star_rating"], "category": a["category"],
             "relevance": a["relevance"]}
            for a in sorted(relevant, key=lambda x: -x["rating_count"])[:5]
        ],
    }


def main():
    all_keywords = list(dict.fromkeys(KW1 + KW2 + KW3 + KW4))  # preserve order, dedupe
    print(f"Total unique keywords: {len(all_keywords)}", flush=True)

    cache = {}
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH) as f:
            cache = json.load(f)
        print(f"Loaded {len(cache)} cached entries", flush=True)

    results = []
    start = time.time()
    new_fetches = 0

    for i, kw in enumerate(all_keywords):
        normed = normalize_keyword(kw)

        if normed in cache and "top10" in cache[normed]:
            top10 = cache[normed]["top10"]
        else:
            try:
                raw = search_apps(normed, limit=25)
                top10 = capture_top10(raw)
                cache[normed] = {"top10": top10, "fetched_at": NOW.isoformat()}
                new_fetches += 1
                time.sleep(0.5)
            except Exception as e:
                print(f"  [{i+1}/{len(all_keywords)}] ERROR {normed}: {e}", flush=True)
                results.append({
                    "keyword_original": kw,
                    "keyword_normalized": normed,
                    "error": str(e),
                })
                continue

            if new_fetches > 0 and new_fetches % 25 == 0:
                with open(CACHE_PATH, "w") as f:
                    json.dump(cache, f)

        results.append(evaluate(kw, top10))

        if (i + 1) % 100 == 0:
            elapsed = time.time() - start
            rate = (i + 1) / elapsed
            remaining = (len(all_keywords) - i - 1) / max(rate, 0.01) / 60
            print(f"[{i+1}/{len(all_keywords)}] rate={rate:.1f}/s "
                  f"eta={remaining:.1f}min new_fetches={new_fetches}", flush=True)

    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f)

    # Sort: off-intent to the bottom, then by ease of entry + demand
    def sort_key(r):
        if "error" in r:
            return (99, 0)
        if r["intent_relevance"] < 0.30:
            return (5, 0)
        verdict_rank = {
            "GREAT": 0, "GOOD": 1, "COMPETITIVE": 2, "NICHE": 3,
            "HARD": 4, "UNPROVEN": 5, "THIN": 6, "AVOID": 7,
            "OFF-INTENT": 8, "UNCERTAIN": 9,
        }
        first_word = r["verdict"].split()[0].rstrip("—").strip()
        rk = verdict_rank.get(first_word, 10)
        # within bucket, sort by relevant demand descending
        demand_order = {"VERY HIGH": 0, "HIGH": 1, "MODERATE": 2, "LOW": 3,
                        "VERY LOW": 4, "NONE": 5}
        return (rk, demand_order.get(r["demand_rel_label"], 9))

    results.sort(key=sort_key)

    with open(OUT_PATH, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nSaved {len(results)} rows → {OUT_PATH}", flush=True)

    # Summary by verdict
    from collections import Counter
    verdict_counts = Counter(
        r["verdict"].split("—")[0].strip() for r in results if "verdict" in r
    )
    print("\nVerdict distribution:")
    for v, c in verdict_counts.most_common():
        print(f"  {c:4}  {v}")

    # Biggest rank-changers: high old demand but off-intent
    print("\nTop 30 FALSE POSITIVES (old demand HIGH/VERY HIGH but off-intent):")
    false_pos = [r for r in results
                 if r.get("intent_relevance", 1) < 0.30
                 and r.get("all_demand_label") in ("HIGH", "VERY HIGH")]
    false_pos.sort(key=lambda r: -r.get("all_total_ratings", 0))
    for r in false_pos[:30]:
        print(f"  rel={r['intent_relevance']:.1f}  "
              f"all_demand={r['all_demand_label']:<10}  "
              f"rel_demand={r['demand_rel_label']:<10}  "
              f"{r['keyword_normalized']}")

    print("\nTop 30 GENUINE OPPORTUNITIES (high intent relevance + real demand + easy):")
    genuine = [r for r in results
               if r.get("intent_relevance", 0) >= 0.5
               and r.get("demand_rel_label") in ("HIGH", "VERY HIGH", "MODERATE")
               and r.get("ease_of_entry", {}).get("label", "").startswith(("EASY", "MODERATE"))]
    for r in genuine[:30]:
        print(f"  rel={r['intent_relevance']:.1f}  "
              f"demand={r['demand_rel_label']:<10}  "
              f"ease={r['ease_of_entry']['label'][:30]:30}  "
              f"{r['keyword_normalized']}")


if __name__ == "__main__":
    main()
