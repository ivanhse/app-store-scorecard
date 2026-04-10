import requests
import time
from datetime import datetime


ITUNES_SEARCH_URL = "https://itunes.apple.com/search"


def search_apps(keyword, country="us", limit=25):
    """Search App Store for a keyword, return top apps with competition data."""
    resp = requests.get(ITUNES_SEARCH_URL, params={
        "term": keyword,
        "entity": "software",
        "country": country,
        "limit": limit,
    }, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    apps = []
    for r in data.get("results", []):
        released = r.get("releaseDate", "")
        updated = r.get("currentVersionReleaseDate", "")
        apps.append({
            "name": r.get("trackName", ""),
            "developer": r.get("artistName", ""),
            "rating_count": r.get("userRatingCount", 0),
            "star_rating": round(r.get("averageUserRating", 0), 1),
            "price": r.get("price", 0),
            "released": released[:10] if released else "?",
            "last_updated": updated[:10] if updated else "?",
            "category": r.get("primaryGenreName", ""),
            "url": r.get("trackViewUrl", ""),
            "bundle_id": r.get("bundleId", ""),
            "app_id": r.get("trackId"),
        })

    return apps


def analyze_competition(apps, top_n=10):
    """Analyze competition from top search results."""
    top = apps[:top_n]
    if not top:
        return {"error": "No apps found"}

    rating_counts = [a["rating_count"] for a in top]
    all_rating_counts = [a["rating_count"] for a in apps]
    star_ratings = [a["star_rating"] for a in top if a["star_rating"] > 0]

    now = datetime.now()
    ages_months = []
    for a in top:
        try:
            rel = datetime.strptime(a["released"], "%Y-%m-%d")
            ages_months.append((now - rel).days / 30)
        except ValueError:
            pass

    stale_count = 0
    for a in top:
        try:
            upd = datetime.strptime(a["last_updated"], "%Y-%m-%d")
            if (now - upd).days > 365:
                stale_count += 1
        except ValueError:
            pass

    avg_ratings = sum(rating_counts) / len(rating_counts)
    max_ratings = max(rating_counts)
    min_ratings = min(rating_counts)
    avg_stars = round(sum(star_ratings) / len(star_ratings), 1) if star_ratings else 0

    # --- DEMAND signals ---
    total_ratings_all = sum(all_rating_counts)
    # How big is this market (sum of all visible apps' reviews)
    if total_ratings_all > 500000:
        demand_level = "VERY HIGH"
    elif total_ratings_all > 100000:
        demand_level = "HIGH"
    elif total_ratings_all > 30000:
        demand_level = "MODERATE"
    elif total_ratings_all > 5000:
        demand_level = "LOW"
    else:
        demand_level = "VERY LOW"

    # --- SUPPLY signals ---
    # How strong are the incumbents you'd compete against
    weak_apps_in_top25 = sum(1 for r in all_rating_counts if r < 1000)
    if avg_ratings > 50000:
        supply_level = "VERY HIGH"
    elif avg_ratings > 10000:
        supply_level = "HIGH"
    elif avg_ratings > 3000:
        supply_level = "MODERATE"
    elif avg_ratings > 500:
        supply_level = "LOW"
    else:
        supply_level = "VERY LOW"

    # --- OPPORTUNITY verdict ---
    demand_rank = ["VERY LOW", "LOW", "MODERATE", "HIGH", "VERY HIGH"].index(demand_level)
    supply_rank = ["VERY LOW", "LOW", "MODERATE", "HIGH", "VERY HIGH"].index(supply_level)
    gap = demand_rank - supply_rank  # positive = demand > supply = opportunity

    if gap >= 2:
        opportunity = "GREAT OPPORTUNITY"
    elif gap == 1:
        opportunity = "GOOD OPPORTUNITY"
    elif gap == 0 and demand_rank >= 3:
        opportunity = "COMPETITIVE — differentiate to win"
    elif gap == 0 and demand_rank <= 1:
        opportunity = "SMALL NICHE — low risk, low reward"
    elif gap == -1:
        opportunity = "OVERSUPPLIED — strong apps, limited demand"
    else:
        opportunity = "AVOID — dominated market"

    # --- MATURE APPS in top 20 (older than 3 years) ---
    top20 = apps[:20]
    mature_count = 0
    top20_with_date = 0
    for a in top20:
        try:
            rel = datetime.strptime(a["released"], "%Y-%m-%d")
            top20_with_date += 1
            if (now - rel).days > 3 * 365:
                mature_count += 1
        except ValueError:
            pass
    mature_apps_pct = round(mature_count / top20_with_date * 100) if top20_with_date else None

    # --- CONCENTRATION INDEX (Gini coefficient of ratings in top 20) ---
    # 0 = perfectly equal, 1 = one app has everything
    top20_ratings = sorted([a["rating_count"] for a in top20])
    n = len(top20_ratings)
    if n > 0 and sum(top20_ratings) > 0:
        cumulative = sum((2 * (i + 1) - n - 1) * val for i, val in enumerate(top20_ratings))
        gini = round(cumulative / (n * sum(top20_ratings)), 2)
    else:
        gini = None

    return {
        "total_results": len(apps),
        "top_n": len(top),
        # Demand
        "demand_level": demand_level,
        "total_ratings_all": total_ratings_all,
        "max_rating_count": max_ratings,
        # Supply
        "supply_level": supply_level,
        "avg_rating_count": int(avg_ratings),
        "min_rating_count": min_ratings,
        "weak_apps_in_top25": weak_apps_in_top25,
        # Quality
        "avg_star_rating": avg_stars,
        "avg_age_months": round(sum(ages_months) / len(ages_months)) if ages_months else None,
        "stale_apps": stale_count,
        "low_rated_apps": sum(1 for s in star_ratings if s < 3.5),
        # Market structure
        "mature_apps_pct": mature_apps_pct,
        "concentration_index": gini,
        # Verdict
        "opportunity": opportunity,
    }
