#!/usr/bin/env python3
"""App Store Scorecard — local web app."""

from flask import Flask, request, jsonify, send_from_directory
from itunes_api import search_apps, analyze_competition
from relevance_rescore import evaluate as relevance_evaluate
import os
import json

app = Flask(__name__, static_folder="static")

# Industry benchmarks by App Store category (sources: Revealbot, Statista, AppsFlyer, Liftoff 2025)
# CPM = cost per 1000 impressions on Meta, CPC = Google Ads cost per click
# CVR = conversion rate (click/impression to install), CPI = effective cost per install
BENCHMARKS = {
    "Games":              {"meta_cpm": 12.0, "google_cpc": 0.60, "meta_cvr": 3.5, "google_cvr": 30.0, "meta_cpi": 3.43, "google_cpi": 2.00},
    "Health & Fitness":   {"meta_cpm": 10.0, "google_cpc": 1.20, "meta_cvr": 2.5, "google_cvr": 25.0, "meta_cpi": 4.00, "google_cpi": 4.80},
    "Finance":            {"meta_cpm": 14.0, "google_cpc": 2.50, "meta_cvr": 2.0, "google_cvr": 20.0, "meta_cpi": 7.00, "google_cpi": 12.50},
    "Utilities":          {"meta_cpm":  7.0, "google_cpc": 0.80, "meta_cvr": 3.0, "google_cvr": 35.0, "meta_cpi": 2.33, "google_cpi": 2.29},
    "Lifestyle":          {"meta_cpm":  9.0, "google_cpc": 1.00, "meta_cvr": 2.8, "google_cvr": 28.0, "meta_cpi": 3.21, "google_cpi": 3.57},
    "Productivity":       {"meta_cpm": 10.0, "google_cpc": 1.50, "meta_cvr": 2.2, "google_cvr": 25.0, "meta_cpi": 4.55, "google_cpi": 6.00},
    "Education":          {"meta_cpm":  8.0, "google_cpc": 1.00, "meta_cvr": 3.0, "google_cvr": 30.0, "meta_cpi": 2.67, "google_cpi": 3.33},
    "Social Networking":  {"meta_cpm": 11.0, "google_cpc": 1.30, "meta_cvr": 2.5, "google_cvr": 22.0, "meta_cpi": 4.40, "google_cpi": 5.91},
    "Medical":            {"meta_cpm": 12.0, "google_cpc": 2.00, "meta_cvr": 1.8, "google_cvr": 20.0, "meta_cpi": 6.67, "google_cpi": 10.00},
    "Business":           {"meta_cpm": 13.0, "google_cpc": 2.00, "meta_cvr": 2.0, "google_cvr": 22.0, "meta_cpi": 6.50, "google_cpi": 9.09},
    "Navigation":         {"meta_cpm":  8.0, "google_cpc": 0.90, "meta_cvr": 3.0, "google_cvr": 32.0, "meta_cpi": 2.67, "google_cpi": 2.81},
    "Photo & Video":      {"meta_cpm": 10.0, "google_cpc": 0.70, "meta_cvr": 3.5, "google_cvr": 35.0, "meta_cpi": 2.86, "google_cpi": 2.00},
    "Food & Drink":       {"meta_cpm":  9.0, "google_cpc": 1.10, "meta_cvr": 2.5, "google_cvr": 25.0, "meta_cpi": 3.60, "google_cpi": 4.40},
    "Travel":             {"meta_cpm": 11.0, "google_cpc": 1.50, "meta_cvr": 2.2, "google_cvr": 22.0, "meta_cpi": 5.00, "google_cpi": 6.82},
    "Entertainment":      {"meta_cpm":  9.0, "google_cpc": 0.80, "meta_cvr": 3.0, "google_cvr": 30.0, "meta_cpi": 3.00, "google_cpi": 2.67},
    "Shopping":           {"meta_cpm": 10.0, "google_cpc": 1.20, "meta_cvr": 2.5, "google_cvr": 25.0, "meta_cpi": 4.00, "google_cpi": 4.80},
    "Reference":          {"meta_cpm":  7.0, "google_cpc": 0.90, "meta_cvr": 2.8, "google_cvr": 28.0, "meta_cpi": 2.50, "google_cpi": 3.21},
    "_default":           {"meta_cpm":  9.0, "google_cpc": 1.00, "meta_cvr": 2.5, "google_cvr": 25.0, "meta_cpi": 3.60, "google_cpi": 4.00},
}


# Curated keyword list sourced from /Users/ivansamsurin/Documents/brainstorms/mobile-apps
# Each entry: (keyword, theme)
OPPORTUNITY_KEYWORDS = [
    # Boring utilities
    ("qr code generator", "Boring utilities"),
    ("voice transcription", "Boring utilities"),
    ("document scanner", "Boring utilities"),
    ("receipt scanner", "Boring utilities"),
    ("construction calculator", "Boring utilities"),
    ("weather alerts", "Boring utilities"),
    ("heic converter", "Boring utilities"),
    ("whiteboard scanner", "Boring utilities"),
    # Vertical AI productivity
    ("ai medical scribe", "Vertical AI"),
    ("ai legal assistant", "Vertical AI"),
    ("landlord app", "Vertical AI"),
    ("realtor crm", "Vertical AI"),
    ("podcast transcription", "Vertical AI"),
    ("hvac estimator", "Vertical AI"),
    ("vet notes", "Vertical AI"),
    # Sleep & circadian
    ("shift work sleep", "Sleep"),
    ("baby sleep schedule", "Sleep"),
    ("cbt-i", "Sleep"),
    ("snoring tracker", "Sleep"),
    # Femtech
    ("pcos tracker", "Femtech"),
    ("pelvic floor", "Femtech"),
    ("cycle tracking", "Femtech"),
    # Senior / aging-in-place
    ("caregiver app", "Senior"),
    ("medication reminder", "Senior"),
    ("senior social", "Senior"),
    # Trucker / owner-operator
    ("load calculator", "Trucker"),
    ("ifta tracker", "Trucker"),
    ("fuel card", "Trucker"),
    ("settlement scanner", "Trucker"),
    ("truck maintenance", "Trucker"),
    # Mental health & cognitive
    ("anxiety app", "Mental health"),
    ("memory training", "Cognitive"),
]

# Rank opportunity verdict from best to worst for sorting
OPPORTUNITY_ORDER = {
    "GREAT OPPORTUNITY": 5,
    "GOOD OPPORTUNITY": 4,
    "COMPETITIVE — differentiate to win": 3,
    "SMALL NICHE — low risk, low reward": 2,
    "OVERSUPPLIED — strong apps, limited demand": 1,
    "AVOID — dominated market": 0,
}
DEMAND_ORDER = {"VERY LOW": 0, "LOW": 1, "MODERATE": 2, "HIGH": 3, "VERY HIGH": 4}


def _score_result(r):
    a = r["analysis"]
    return (OPPORTUNITY_ORDER.get(a["opportunity"], -1), DEMAND_ORDER.get(a["demand_level"], 0))


def _analyze_keyword(kw, country, limit):
    apps = search_apps(kw, country=country, limit=limit)
    analysis = analyze_competition(apps)
    display_apps = apps[:limit]
    try:
        relevance = relevance_evaluate(kw, apps[:10])
    except Exception as e:
        relevance = {"error": str(e)}

    rating_counts = sorted([a["rating_count"] for a in apps])
    p25 = rating_counts[len(rating_counts) // 4] if len(rating_counts) >= 4 else 0
    p50 = rating_counts[len(rating_counts) // 2] if len(rating_counts) >= 2 else 0
    p75 = rating_counts[3 * len(rating_counts) // 4] if len(rating_counts) >= 4 else 0

    free_count = sum(1 for a in apps if a["price"] == 0)

    star_buckets = {"4.5+": 0, "4.0-4.4": 0, "3.5-3.9": 0, "<3.5": 0}
    for a in apps:
        s = a["star_rating"]
        if s >= 4.5:
            star_buckets["4.5+"] += 1
        elif s >= 4.0:
            star_buckets["4.0-4.4"] += 1
        elif s >= 3.5:
            star_buckets["3.5-3.9"] += 1
        else:
            star_buckets["<3.5"] += 1

    cat_counts = {}
    for a in apps:
        c = a.get("category", "")
        cat_counts[c] = cat_counts.get(c, 0) + 1
    dominant_cat = max(cat_counts, key=cat_counts.get) if cat_counts else "_default"
    benchmarks = BENCHMARKS.get(dominant_cat, BENCHMARKS["_default"])

    return {
        "keyword": kw,
        "apps": display_apps,
        "analysis": analysis,
        "relevance": relevance,
        "percentiles": {"p25": p25, "p50": p50, "p75": p75},
        "free_vs_paid": {"free": free_count, "paid": len(apps) - free_count},
        "star_distribution": star_buckets,
        "category": dominant_cat,
        "benchmarks": benchmarks,
    }


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/opportunities", methods=["GET"])
def opportunities():
    country = request.args.get("country", "us")
    results = []
    for kw, theme in OPPORTUNITY_KEYWORDS:
        try:
            r = _analyze_keyword(kw, country, 25)
            r["theme"] = theme
            results.append(r)
        except Exception as e:
            results.append({"keyword": kw, "theme": theme, "error": str(e)})

    results.sort(key=lambda r: _score_result(r) if "error" not in r else (-1, -1), reverse=True)
    return jsonify(results)


@app.route("/api/analyze", methods=["POST"])
def analyze():
    data = request.json
    keywords = data.get("keywords", [])
    country = data.get("country", "us")
    limit = data.get("limit", 25)

    if not keywords:
        return jsonify({"error": "No keywords provided"}), 400

    results = [_analyze_keyword(kw, country, limit) for kw in keywords]
    return jsonify(results)


@app.route("/api/shortlist", methods=["GET"])
def shortlist():
    results_path = os.path.join(os.path.dirname(__file__), "shortlist_analysis.json")
    if not os.path.exists(results_path):
        return jsonify({"error": "shortlist_analysis.json not found"}), 404
    with open(results_path) as f:
        data = json.load(f)
    return jsonify(data)


@app.route("/api/deep-research", methods=["GET"])
def deep_research():
    results_path = os.path.join(os.path.dirname(__file__), "deep_research.json")
    if not os.path.exists(results_path):
        return jsonify({"error": "deep_research.json not found — run deep_research.py first"}), 404
    with open(results_path) as f:
        data = json.load(f)
    return jsonify(data)


@app.route("/api/clusters", methods=["GET"])
def clusters():
    results_path = os.path.join(os.path.dirname(__file__), "clusters.json")
    if not os.path.exists(results_path):
        return jsonify({"error": "clusters.json not found — run build_clusters.py first"}), 404
    with open(results_path) as f:
        data = json.load(f)
    return jsonify(data)


@app.route("/api/research", methods=["GET"])
def research():
    tier = request.args.get("tier", "all")
    results_path = os.path.join(os.path.dirname(__file__), "batch_results.json")
    if not os.path.exists(results_path):
        return jsonify({"error": "batch_results.json not found — run batch_evaluate.py first"}), 404
    with open(results_path) as f:
        data = json.load(f)
    tier = tier.replace(" ", "+")
    if tier == "great":
        data = [r for r in data if "GREAT" in r.get("opportunity", "")]
    elif tier == "good":
        data = [r for r in data if "GOOD" in r.get("opportunity", "") and "GREAT" not in r.get("opportunity", "")]
    elif tier == "great+good":
        data = [r for r in data if "GREAT" in r.get("opportunity", "") or "GOOD" in r.get("opportunity", "")]
    return jsonify(data)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5555))
    app.run(host="0.0.0.0", port=port)
