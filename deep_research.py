#!/usr/bin/env python3
"""Deep-research re-scan of batch_results.json.

- Strips " app" / " apps" suffix (people don't search "photos app" on App Store)
- Re-queries iTunes with limit=25 for richer signals
- Enriches with price mix, category concentration, incumbent detection
- Applies critical-thinking classifier (kill/win patterns)
- Produces re-ranked vibe-ROI list.
"""

import json
import os
import re
import sys
import time
from datetime import datetime

import requests

ITUNES = "https://itunes.apple.com/search"
NOW = datetime.now()

# Known dominant incumbents — seeing any of these in top-3 hard-caps opportunity
DOMINANT_INCUMBENTS = {
    "splitwise", "forest", "todoist", "things 3", "notion", "evernote",
    "coolors", "adobe color", "yuka", "good on you", "typeform",
    "surveymonkey", "google forms", "myfitnesspal", "calm", "headspace",
    "duolingo", "babbel", "rosetta stone", "strava", "nike run club",
    "venmo", "paypal", "cash app", "zelle", "google translate",
    "instagram", "tiktok", "snapchat", "whatsapp", "messenger", "telegram",
    "waze", "google maps", "apple maps", "spotify", "apple music",
    "youtube", "netflix", "hulu", "disney+", "hbo max",
    "canva", "adobe express", "procreate", "photoshop",
    "microsoft word", "microsoft excel", "google docs", "google sheets",
    "pinterest", "reddit", "quora", "linkedin", "facebook",
    "amazon", "ebay", "etsy", "target", "walmart",
    "tinder", "bumble", "hinge", "match", "okcupid",
    "robinhood", "coinbase", "binance", "webull",
    "doordash", "uber eats", "grubhub", "instacart",
    "uber", "lyft", "waymo",
    "clash royale", "clash of clans", "candy crush", "roblox", "minecraft",
    "fitbit", "garmin connect", "oura",
    "1password", "lastpass", "bitwarden", "nordvpn", "expressvpn",
    "zoom", "microsoft teams", "slack",
    "google chrome", "firefox", "microsoft edge", "brave",
    "shazam", "soundhound",
    "chatgpt", "claude", "gemini", "copilot",
    "dropbox", "google drive", "onedrive", "icloud",
    "mint", "ynab", "rocket money", "credit karma", "nerdwallet",
    "allrecipes", "yummly", "paprika",
    "cookpad", "tasty",
    "kindle", "audible", "libby", "scribd", "goodreads",
    "quizlet", "khan academy", "photomath", "mathway",
    "abc mouse", "khan kids", "pbs kids",
    "ring", "nest", "wyze",
    "1weather", "weather channel", "accuweather", "carrot weather",
    "tripit", "expedia", "kayak", "hopper", "airbnb", "vrbo", "booking.com",
    "life360", "find my",
    "my disney experience", "my universal", "universal orlando",
    "rootd", "bearable", "daylio", "moodnotes",
    "flo", "clue", "glow", "stardust",
    "huckleberry", "wonder weeks",
    "sleep cycle", "pillow", "autosleep",
    "insight timer", "balance",
    "notability", "goodnotes", "noteshelf",
    "ios mail", "outlook", "gmail",
    "microsoft authenticator", "google authenticator", "authy",
    "mycar", "carfax", "autotrader",
    "pokémon go", "pokemon go", "monster hunter now",
    "tiktok", "reels",
    "anki", "anki mobile",
    "coinbase wallet", "metamask", "trust wallet",
}

# Keyword-level kill patterns — regex-matched against the normalized keyword
KILL_PATTERNS = [
    # One-shot calculators — browser/Google solves, zero retention
    (r"\b(calculator|converter|estimator)\b", "one_shot_calc"),
    (r"\b(tip split|bill split|restaurant tip|split the bill)\b", "one_shot_split"),
    # iOS built-in kills
    (r"\b(flashlight|compass|level|ruler|magnifier|timezone|world clock|alarm clock|stopwatch)\b", "ios_builtin"),
    (r"\b(clipboard|paste board)\b", "ios_sandbox"),
    # Free alternatives dominate
    (r"\b(encyclopedia|wikipedia|thesaurus)\b", "free_alt_dominant"),
    # Medical / legal liability
    (r"\b(diagnosis|symptom checker|prescription|medical advice|legal advice)\b", "liability"),
    # Dating / social networks — network-effect dominated
    (r"\b(dating|hookup|matchmaking)\b", "network_effect_lock"),
    # One-shot B2B construction browsed
    (r"\b(concrete calculator|rebar|framing calculator|roofing calculator|drywall calculator)\b", "b2b_oneshot"),
    # Generic "best X" lists / informational
    (r"^(best|top) ", "informational_intent"),
]

# Win patterns — reasons to weight higher
WIN_PATTERNS = [
    (r"\b(tracker|logger|log|diary|journal)\b", "sticky_tracker", 1.25),
    (r"\b(baby|newborn|infant|toddler|kids|child|homework|chore|parent|caregiver)\b", "parent_wtp", 1.20),
    (r"\b(couple|couples|relationship|marriage)\b", "couples_wtp", 1.15),
    (r"\b(fishing|knitting|woodworking|aquarium|gardening|birdwatching|birding|stargazing|beekeeping|coin collect|stamp collect|rock identif|plant identif|mushroom identif)\b", "hobby_wtp", 1.20),
    (r"\b(trucker|owner operator|realtor|hvac|landlord|airbnb host|contractor|electrician|plumber)\b", "niche_pro_wtp", 1.25),
    (r"\b(ai (scribe|legal|resume|coach|tutor|cover letter|lease|contract))\b", "vertical_ai", 1.30),
    (r"\b(sleep|snor|cbt-i|circadian|insomnia)\b", "sleep_wtp", 1.15),
    (r"\b(pcos|cycle|pelvic|menopause|perimenopause|fertility)\b", "femtech_wtp", 1.20),
    (r"\b(medication reminder|pill reminder|pill tracker)\b", "med_reminder", 1.15),
]

# Category → ARPU proxy (monthly subscription potential in $ if converted)
CATEGORY_ARPU = {
    "Health & Fitness": 7.0,
    "Finance": 10.0,
    "Medical": 8.0,
    "Lifestyle": 5.0,
    "Productivity": 6.0,
    "Education": 6.0,
    "Business": 10.0,
    "Photo & Video": 5.0,
    "Utilities": 4.0,
    "Navigation": 4.0,
    "Food & Drink": 5.0,
    "Games": 4.0,
    "Social Networking": 3.0,
    "Entertainment": 5.0,
    "Travel": 5.0,
    "Reference": 3.0,
    "Shopping": 3.0,
    "News": 3.0,
    "Weather": 4.0,
    "Sports": 4.0,
    "Music": 4.0,
    "Book": 3.0,
}

# Category → effective CPI (median of Meta/Google from BENCHMARKS)
CATEGORY_CPI = {
    "Health & Fitness": 4.40,
    "Finance": 9.75,
    "Medical": 8.33,
    "Lifestyle": 3.39,
    "Productivity": 5.28,
    "Education": 3.00,
    "Business": 7.80,
    "Photo & Video": 2.43,
    "Utilities": 2.31,
    "Navigation": 2.74,
    "Food & Drink": 4.00,
    "Games": 2.72,
    "Social Networking": 5.16,
    "Entertainment": 2.84,
    "Travel": 5.91,
    "Reference": 2.86,
    "Shopping": 4.40,
    "News": 3.50,
    "Weather": 3.00,
    "Sports": 3.50,
    "Music": 3.00,
    "Book": 3.00,
}

DEFAULT_ARPU = 4.0
DEFAULT_CPI = 3.50


def normalize_keyword(kw):
    kw = kw.lower().strip()
    for suf in [" apps", " app"]:
        if kw.endswith(suf):
            kw = kw[: -len(suf)].strip()
    return kw


def search_apps(keyword, country="us", limit=25, retries=5):
    for attempt in range(retries):
        try:
            r = requests.get(
                ITUNES,
                params={"term": keyword, "entity": "software", "country": country, "limit": limit},
                timeout=20,
            )
            if r.status_code == 429:
                # Exponential backoff on rate limit
                time.sleep(5 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json().get("results", [])
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(3 * (attempt + 1))


def enrich(keyword, raw_results):
    """Compute demand/supply/quality signals for a keyword's search results."""
    apps = []
    for r in raw_results:
        released = r.get("releaseDate", "")
        updated = r.get("currentVersionReleaseDate", "")
        apps.append({
            "name": r.get("trackName", ""),
            "developer": r.get("artistName", ""),
            "rating_count": r.get("userRatingCount", 0) or 0,
            "star_rating": round(r.get("averageUserRating", 0) or 0, 1),
            "price": r.get("price", 0) or 0,
            "released": released[:10] if released else "",
            "last_updated": updated[:10] if updated else "",
            "category": r.get("primaryGenreName", ""),
        })

    if not apps:
        return None

    top10 = apps[:10]
    rc = [a["rating_count"] for a in top10]
    total_r = sum(rc)
    avg_r = total_r / len(rc) if rc else 0
    max_r = max(rc) if rc else 0

    # Demand levels
    if total_r > 300000:
        demand = "VERY HIGH"
    elif total_r > 60000:
        demand = "HIGH"
    elif total_r > 15000:
        demand = "MODERATE"
    elif total_r > 3000:
        demand = "LOW"
    else:
        demand = "VERY LOW"

    if avg_r > 50000:
        supply = "VERY HIGH"
    elif avg_r > 10000:
        supply = "HIGH"
    elif avg_r > 3000:
        supply = "MODERATE"
    elif avg_r > 500:
        supply = "LOW"
    else:
        supply = "VERY LOW"

    weak_top10 = sum(1 for x in rc if x < 1000)

    # Gini
    sorted_rc = sorted(rc)
    n = len(sorted_rc)
    if n > 0 and sum(sorted_rc) > 0:
        cum = sum((2 * (i + 1) - n - 1) * v for i, v in enumerate(sorted_rc))
        gini = round(cum / (n * sum(sorted_rc)), 2)
    else:
        gini = 0

    # Category mode
    cats = {}
    for a in apps:
        c = a.get("category") or ""
        cats[c] = cats.get(c, 0) + 1
    dominant_cat = max(cats, key=cats.get) if cats else ""
    # Category concentration (how focused is search intent)
    cat_focus = round(cats.get(dominant_cat, 0) / max(len(apps), 1), 2)

    # Price mix
    free = sum(1 for a in top10 if a["price"] == 0)
    paid = len(top10) - free

    # Avg stars
    stars = [a["star_rating"] for a in top10 if a["star_rating"] > 0]
    avg_stars = round(sum(stars) / len(stars), 2) if stars else 0

    # Staleness / maturity
    stale, mature, have_date = 0, 0, 0
    for a in top10:
        try:
            upd = datetime.strptime(a["last_updated"], "%Y-%m-%d")
            if (NOW - upd).days > 365:
                stale += 1
        except ValueError:
            pass
        try:
            rel = datetime.strptime(a["released"], "%Y-%m-%d")
            have_date += 1
            if (NOW - rel).days > 3 * 365:
                mature += 1
        except ValueError:
            pass
    mature_pct = round(mature / have_date * 100) if have_date else 0

    # Dominant incumbent detection — word-boundary match on top-3 app names
    top3_names = [a["name"].lower() for a in top10[:3]]
    incumbent = None
    for name in top3_names:
        tokens = re.split(r"[^a-z0-9+]+", name)
        token_set = set(t for t in tokens if t)
        for dom in DOMINANT_INCUMBENTS:
            dom_tokens = dom.split()
            # Match only if all incumbent name tokens appear as whole words in the app name
            if all(t in token_set for t in dom_tokens):
                incumbent = dom
                break
        if incumbent:
            break

    return {
        "total_ratings_top10": total_r,
        "max_rating_count": max_r,
        "avg_rating_count": int(avg_r),
        "weak_apps_in_top10": weak_top10,
        "avg_star_rating": avg_stars,
        "concentration_index": gini,
        "dominant_category": dominant_cat,
        "category_focus": cat_focus,
        "free_count": free,
        "paid_count": paid,
        "stale_apps": stale,
        "mature_apps_pct": mature_pct,
        "demand_level": demand,
        "supply_level": supply,
        "incumbent": incumbent,
        "top3": [
            {"name": a["name"], "rating_count": a["rating_count"],
             "star_rating": a["star_rating"], "price": a["price"],
             "developer": a["developer"], "category": a["category"]}
            for a in top10[:3]
        ],
        "top10_names": [a["name"] for a in top10],
    }


def classify(keyword, signals):
    """Apply kill/win patterns. Returns (kills, wins, reasons, penalty_mult, boost_mult)."""
    kills, wins, reasons = [], [], []
    penalty = 1.0
    boost = 1.0

    # Keyword-level kill patterns
    for pat, tag in KILL_PATTERNS:
        if re.search(pat, keyword, re.I):
            kills.append(tag)
            reasons.append(f"kill:{tag}")

    # Keyword-level win patterns
    for pat, tag, mult in WIN_PATTERNS:
        if re.search(pat, keyword, re.I):
            wins.append(tag)
            boost *= mult
            reasons.append(f"win:{tag}(x{mult})")

    # Signal-level kills
    if signals.get("incumbent"):
        kills.append(f"incumbent:{signals['incumbent']}")
        penalty *= 0.35
        reasons.append(f"kill:incumbent={signals['incumbent']}")

    if signals.get("category_focus", 0) < 0.35:
        kills.append("fuzzy_intent")
        penalty *= 0.7
        reasons.append("kill:fuzzy_search_intent")

    if signals.get("concentration_index", 0) > 0.80 and signals.get("max_rating_count", 0) > 50000:
        kills.append("concentrated_top")
        penalty *= 0.6
        reasons.append("kill:one_app_owns_category")

    # Off-intent detection: huge total ratings but top-1 is not really about the keyword.
    # Heuristic: if concentration > 0.75 and max_rating > 30k, one app dominates with something
    # tangentially related. Example: "charitable giving tracker" → Givelify donation app.
    if (signals.get("concentration_index", 0) > 0.75
            and signals.get("max_rating_count", 0) > 30000
            and signals.get("max_rating_count", 0) > 5 * signals.get("avg_rating_count", 1)):
        kills.append("off_intent_dominant")
        penalty *= 0.4
        reasons.append("kill:off_intent_single_app_hijacks_search")

    # Budget-app cannibalization: finance-ish "tracker" / "budget" / "expense" categories
    # are eaten by Mint / YNAB / Rocket Money / Copilot / Honeydue / Monarch.
    budget_eaters = {"ynab", "mint", "rocket money", "copilot", "honeydue", "monarch",
                      "credit karma", "nerdwallet", "simplifi", "emma", "empower"}
    top3 = signals.get("top3", [])
    has_budget_eater = False
    for a in top3:
        name = (a.get("name") or "").lower()
        tokens = set(re.split(r"[^a-z0-9+]+", name))
        for eater in budget_eaters:
            if all(t in tokens for t in eater.split()):
                has_budget_eater = True
                kills.append(f"budget_app_eats:{eater}")
                reasons.append(f"kill:budget_app_cannibalizes({eater})")
                break
        if has_budget_eater:
            break
    if has_budget_eater:
        penalty *= 0.4

    # Tracker-in-finance deflation: keyword has "tracker"/"log" + dominant category Finance
    # and tax-adjacent → low retention, yearly use, budget apps cover.
    if ("sticky_tracker" in wins
            and signals.get("dominant_category") == "Finance"
            and "vertical_ai" not in wins
            and "niche_pro_wtp" not in wins):
        # Undo the sticky boost for generic finance trackers
        boost /= 1.25
        reasons.append("adj:finance_tracker_not_sticky")
        if "sticky_tracker" in wins:
            wins.remove("sticky_tracker")

    # Tax/annual-use kill: once-a-year keywords cannot retain
    if re.search(r"\b(tax|deduction|annual|yearly|charitable giving|donation)\b", keyword, re.I):
        kills.append("annual_use")
        penalty *= 0.45
        reasons.append("kill:annual_use_not_monthly_retention")

    return kills, wins, reasons, penalty, boost


def compute_vibe_roi(keyword, signals, kills, wins, penalty, boost):
    """Revised vibe-ROI that combines payback economics, retention, and kill penalties."""
    cat = signals.get("dominant_category", "")
    arpu = CATEGORY_ARPU.get(cat, DEFAULT_ARPU)
    cpi = CATEGORY_CPI.get(cat, DEFAULT_CPI)

    # Paying conversion & retention proxies
    paying_conv = 0.05
    retention_months = 6

    # Sticky trackers get better retention
    if "sticky_tracker" in wins or "parent_wtp" in wins:
        retention_months = 9
    if "hobby_wtp" in wins or "niche_pro_wtp" in wins:
        retention_months = 10
        paying_conv = 0.07
    if "vertical_ai" in wins:
        retention_months = 12
        paying_conv = 0.08
    if "couples_wtp" in wins or "sleep_wtp" in wins or "femtech_wtp" in wins:
        retention_months = 8

    # One-shot kills → collapse retention
    if any(k.startswith("one_shot") or k.startswith("b2b_oneshot") or k.startswith("ios_builtin")
           or k.startswith("ios_sandbox") or k.startswith("free_alt") or k.startswith("informational_intent")
           or k.startswith("liability") or k.startswith("network_effect")
           for k in kills):
        retention_months = min(retention_months, 1)
        paying_conv = min(paying_conv, 0.01)

    # LTV and payback
    ltv = arpu * paying_conv * retention_months
    payback_months = cpi / (arpu * paying_conv) if (arpu * paying_conv) > 0 else 999
    roas_6mo = ltv / cpi if cpi > 0 else 0

    # Demand score — normalized by total ratings
    total_r = signals.get("total_ratings_top10", 0)
    demand_log = min(1.0, (total_r / 100000) ** 0.5)  # 100k ratings = max demand signal

    # Supply room — more weak apps + lower gini = more room
    weak = signals.get("weak_apps_in_top10", 0)
    gini = signals.get("concentration_index", 0.5)
    supply_room = (weak / 10) * 0.5 + (1 - gini) * 0.5

    # Base score: LTV × demand × supply_room × boosts × penalties
    base = ltv * (0.5 + demand_log) * (0.4 + supply_room)
    vibe_roi = base * boost * penalty

    return {
        "vibe_roi": round(vibe_roi, 2),
        "ltv": round(ltv, 2),
        "payback_months": round(payback_months, 2),
        "roas_6mo": round(roas_6mo, 2),
        "arpu_est": arpu,
        "cpi_est": cpi,
        "retention_months": retention_months,
        "paying_conv": paying_conv,
        "demand_signal": round(demand_log, 2),
        "supply_room": round(supply_room, 2),
        "boost_mult": round(boost, 2),
        "penalty_mult": round(penalty, 2),
    }


def main():
    inp = "/Users/ivansamsurin/Documents/myprojects/app-store-scorecard/batch_results.json"
    out = "/Users/ivansamsurin/Documents/myprojects/app-store-scorecard/deep_research.json"
    cache = "/Users/ivansamsurin/Documents/myprojects/app-store-scorecard/deep_research_cache.json"

    with open(inp) as f:
        batch = json.load(f)

    # Load cache for resumability
    cached = {}
    if os.path.exists(cache):
        with open(cache) as f:
            cached = json.load(f)

    results = []
    total = len(batch)
    start = time.time()

    for i, row in enumerate(batch):
        original = row["keyword"]
        normed = normalize_keyword(original)

        if normed in cached:
            signals = cached[normed]
        else:
            try:
                raw = search_apps(normed, limit=25)
                signals = enrich(normed, raw) or {}
            except Exception as e:
                print(f"  [{i+1}/{total}] ERROR {normed}: {e}", flush=True)
                signals = {"error": str(e)}
            cached[normed] = signals
            # Save cache every 20 rows
            if (i + 1) % 20 == 0:
                with open(cache, "w") as f:
                    json.dump(cached, f)

            # Rate limit — iTunes Search API throttles aggressively
            time.sleep(0.5)

        if "error" in signals:
            results.append({
                "keyword_original": original,
                "keyword_normalized": normed,
                "error": signals["error"],
            })
            continue

        kills, wins, reasons, penalty, boost = classify(normed, signals)
        roi = compute_vibe_roi(normed, signals, kills, wins, penalty, boost)

        results.append({
            "keyword_original": original,
            "keyword_normalized": normed,
            **signals,
            "kills": kills,
            "wins": wins,
            "reasons": reasons,
            **roi,
        })

        if (i + 1) % 50 == 0:
            elapsed = time.time() - start
            rate = (i + 1) / elapsed
            eta = (total - i - 1) / rate / 60
            print(f"[{i+1}/{total}] rate={rate:.1f}/s eta={eta:.1f}min", flush=True)

    # Final cache save
    with open(cache, "w") as f:
        json.dump(cached, f)

    # Rank by vibe_roi desc (errors to bottom)
    results.sort(key=lambda r: r.get("vibe_roi", -1), reverse=True)

    with open(out, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nSaved {len(results)} rows → {out}")
    print("\nTop 20 by vibe_roi:")
    for r in results[:20]:
        print(f"  {r.get('vibe_roi','?'):>7} | pb={r.get('payback_months','?'):>5}mo | "
              f"{r['keyword_normalized'][:40]:40} | kills={r.get('kills',[])} | wins={r.get('wins',[])}")


if __name__ == "__main__":
    main()
