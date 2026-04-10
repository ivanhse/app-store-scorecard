#!/usr/bin/env python3
"""
App Store Scorecard — estimate demand & competition for app keywords.

Usage:
    python scorecard.py "habit tracker" "sobriety tracker" "meditation app"
    python scorecard.py --country gb "fitness app"
    python scorecard.py --json "budget app"
"""

import argparse
import json
import sys
import time

from itunes_api import search_apps, analyze_competition


def format_number(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def verdict(popularity, competition):
    """Generate a human-readable verdict."""
    if popularity is None:
        # No Search Ads data — verdict based on competition only
        if competition in ("VERY LOW", "LOW"):
            return "LOW COMPETITION — set up Search Ads to check demand"
        if competition == "MODERATE":
            return "MODERATE COMPETITION — set up Search Ads to check demand"
        if competition == "HIGH":
            return "HIGH COMPETITION — need strong differentiation"
        return "VERY HIGH COMPETITION — dominated by incumbents"

    pop = popularity
    if pop >= 50 and competition in ("VERY LOW", "LOW"):
        return "GREAT OPPORTUNITY — high demand, low competition"
    if pop >= 30 and competition in ("VERY LOW", "LOW"):
        return "GOOD OPPORTUNITY — decent demand, low competition"
    if pop >= 50 and competition == "MODERATE":
        return "PROMISING — high demand, moderate competition. Differentiate to win"
    if pop >= 50 and competition in ("HIGH", "VERY HIGH"):
        return "TOUGH MARKET — high demand but dominated by incumbents"
    if pop < 15:
        return "LOW DEMAND — few people search for this"
    if pop < 30 and competition in ("HIGH", "VERY HIGH"):
        return "AVOID — low demand AND high competition"
    return "WORTH INVESTIGATING — moderate signals, dig deeper"


def print_scorecard(keyword, apps, analysis, popularity=None):
    pop_str = str(popularity) if popularity else "N/A (set up Search Ads for this)"
    comp = analysis["competition_level"]
    verd = verdict(popularity, comp)

    print(f"\n{'='*60}")
    print(f"  KEYWORD: \"{keyword}\"")
    print(f"{'='*60}")
    print(f"  Demand (popularity):    {pop_str}")
    print(f"  Competition level:      {comp}")
    print(f"  Top {analysis['top_n']} avg ratings:    {format_number(analysis['avg_rating_count'])}")
    print(f"  Top app ratings:        {format_number(analysis['max_rating_count'])}")
    print(f"  Weakest in top 10:      {format_number(analysis['min_rating_count'])}")
    print(f"  Avg star rating:        {analysis['avg_star_rating']}")
    print(f"  Stale apps (>1yr):      {analysis['stale_apps']}/{analysis['top_n']}")
    print(f"  Low-rated apps (<3.5):  {analysis['low_rated_apps']}/{analysis['top_n']}")
    if analysis["avg_age_months"]:
        print(f"  Avg app age:            {analysis['avg_age_months']} months")
    print(f"  Total results:          {analysis['total_results']}")
    print(f"  {'─'*56}")
    print(f"  VERDICT: {verd}")
    print(f"{'='*60}")

    print(f"\n  Top 10 apps:")
    print(f"  {'#':<3} {'App':<30} {'Ratings':>9} {'Stars':>5} {'Updated':>12}")
    print(f"  {'─'*63}")
    for i, app in enumerate(apps[:10], 1):
        name = app["name"][:28]
        print(f"  {i:<3} {name:<30} {format_number(app['rating_count']):>9} {app['star_rating']:>5} {app['last_updated']:>12}")
    print()


def main():
    parser = argparse.ArgumentParser(description="App Store Keyword Scorecard")
    parser.add_argument("keywords", nargs="+", help="Keywords to analyze")
    parser.add_argument("--country", default="us", help="Country code (default: us)")
    parser.add_argument("--limit", type=int, default=25, help="Max apps per keyword (default: 25)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    # Try loading Search Ads client (optional)
    ads_client = None
    try:
        from search_ads import load_client_from_env
        ads_client = load_client_from_env()
        if ads_client and not args.json:
            print("[+] Apple Search Ads connected — popularity scores enabled")
    except Exception:
        pass

    if not ads_client and not args.json:
        print("[!] Apple Search Ads not configured — showing competition data only")
        print("    Set up .env with your credentials to enable popularity scores")

    results = []

    for keyword in args.keywords:
        if not args.json:
            print(f"\n[*] Analyzing: \"{keyword}\"...")

        # iTunes Search API — competition data
        apps = search_apps(keyword, country=args.country, limit=args.limit)
        analysis = analyze_competition(apps)

        # Apple Search Ads — popularity score (if configured)
        popularity = None
        if ads_client and apps:
            try:
                # Use first result's app_id to get keyword recommendations
                recs = ads_client.get_keyword_recommendations(
                    apps[0]["app_id"], country=args.country.upper()
                )
                # Find our keyword in recommendations
                kw_lower = keyword.lower()
                for rec in recs:
                    if rec["keyword"].lower() == kw_lower:
                        popularity = rec["popularity"]
                        break
                # If exact match not found, use closest match
                if popularity is None:
                    for rec in recs:
                        if kw_lower in rec["keyword"].lower():
                            popularity = rec["popularity"]
                            break
            except Exception as e:
                if not args.json:
                    print(f"    [!] Search Ads error: {e}")

        if args.json:
            results.append({
                "keyword": keyword,
                "popularity": popularity,
                "competition": analysis,
                "top_apps": apps[:10],
            })
        else:
            print_scorecard(keyword, apps, analysis, popularity)

        # Rate limit: iTunes API allows ~20 calls/min
        if keyword != args.keywords[-1]:
            time.sleep(3)

    if args.json:
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
