#!/usr/bin/env python3
"""Group the 1000 keywords into theme clusters.

Each distinctive domain token (intent modifiers like "tracker"/"app"
stripped, and with document frequency between MIN_DF and MAX_DF) becomes
a cluster theme. A keyword appears in every theme bucket it qualifies for,
so "baby sleep tracker" is visible under both the `baby` and `sleep`
themes. No transitive closure, so unrelated topics can't chain-merge.

Singleton keywords (no qualifying theme token) are grouped into a
`(unclustered)` bucket purely so the total is traceable, but hidden from
the UI by default.

For each cluster we surface:
  - size, theme token(s)
  - union of top-10 relevant apps across member keywords (dedupe by name+dev)
  - aggregate rating volume and #unique relevant apps (real competitive footprint)
  - best / worst vibe_roi inside cluster, avg intent_relevance
  - dominant category, best verdict

Output: clusters.json (consumed by /api/clusters).
"""

import json
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from relevance_rescore import (
    normalize_keyword, domain_tokens, stem_lite,
)

DEEP_PATH = os.path.join(ROOT, "deep_research.json")
REL_PATH = os.path.join(ROOT, "relevance_rescored.json")
OUT_PATH = os.path.join(ROOT, "clusters.json")

# A token becomes a theme if it appears in [MIN_DF, MAX_DF] keywords.
# <2 means nothing to cluster. >25 is too broad (e.g. "train", "exercise"
# span unrelated niches and would swallow everything).
MIN_DF = 2
MAX_DF = 25


def verdict_for(row: dict) -> str:
    """Mirror static/index.html deepVerdict()."""
    kills = row.get("kills") or []
    if "off_intent" in kills:
        return "OFF-INTENT"
    v = row.get("vibe_roi") or 0
    if v >= 8:
        return "GREAT OPPORTUNITY"
    if v >= 4:
        return "GOOD OPPORTUNITY"
    if v >= 1.5:
        return "COMPETITIVE"
    if v >= 0.5:
        return "NICHE"
    return "AVOID"


VERDICT_RANK = {
    "GREAT OPPORTUNITY": 6, "GOOD OPPORTUNITY": 5, "COMPETITIVE": 4,
    "NICHE": 3, "AVOID": 2, "OFF-INTENT": 1,
}


def cluster(token_by_kw: dict[str, set]) -> dict[str, list[str]]:
    """Group keywords by each qualifying theme token.

    Returns a dict: theme_token -> list of keyword members. A keyword can
    appear under multiple themes. Keywords with no qualifying token go
    under a single "(unclustered)" bucket so nothing is silently dropped.
    """
    tok_idx: dict[str, list[str]] = defaultdict(list)
    for kw, toks in token_by_kw.items():
        for t in toks:
            tok_idx[t].append(kw)

    groups: dict[str, list[str]] = {}
    covered: set[str] = set()
    for tok, kws in tok_idx.items():
        if len(kws) < MIN_DF or len(kws) > MAX_DF:
            continue
        groups[tok] = sorted(set(kws))
        covered.update(kws)

    singles = [k for k in token_by_kw if k not in covered]
    if singles:
        groups["(unclustered)"] = sorted(singles)
    return groups


def main():
    with open(DEEP_PATH) as f:
        deep = json.load(f)
    with open(REL_PATH) as f:
        rel = json.load(f)

    deep_by_norm = {r["keyword_normalized"]: r for r in deep}
    rel_by_norm = {r["keyword_normalized"]: r for r in rel}

    # Build domain-token sets
    token_by_kw: dict[str, set] = {}
    for r in rel:
        norm = r.get("keyword_normalized")
        if not norm or "error" in r:
            continue
        toks = set(r.get("domain_tokens") or domain_tokens(norm))
        token_by_kw[norm] = toks

    groups = cluster(token_by_kw)
    print(f"Built {len(groups)} theme clusters from {len(token_by_kw)} keywords.")

    clusters = []
    for theme_token, members in groups.items():
        if not members:
            continue

        if theme_token == "(unclustered)":
            theme = set()
        else:
            theme = {theme_token}

        # Aggregate relevant apps across all members, dedupe by (name, developer)
        seen_apps = {}
        for m in members:
            rrel = rel_by_norm.get(m, {})
            for a in rrel.get("top10_scored") or []:
                if a.get("relevance", 0) < 0.5:
                    continue
                key = (a.get("name", ""), a.get("developer", ""))
                prev = seen_apps.get(key)
                if prev is None or a.get("rating_count", 0) > prev.get("rating_count", 0):
                    seen_apps[key] = {
                        "name": a.get("name", ""),
                        "developer": a.get("developer", ""),
                        "rating_count": int(a.get("rating_count") or 0),
                        "star_rating": a.get("star_rating", 0),
                        "category": a.get("category", ""),
                        "appears_in": [],
                    }
                seen_apps[key]["appears_in"].append(m)

        unique_apps = sorted(seen_apps.values(), key=lambda x: -x["rating_count"])
        unique_total_ratings = sum(a["rating_count"] for a in unique_apps)

        # Member-level metrics
        member_rows = []
        intent_sum = 0
        intent_n = 0
        best_verdict_rank = 0
        best_verdict_label = "AVOID"
        best_vibe = 0.0
        worst_vibe = 999.0
        categories = defaultdict(int)

        for m in members:
            d = deep_by_norm.get(m) or {}
            rrel = rel_by_norm.get(m) or {}
            v = verdict_for(d)
            vr = d.get("vibe_roi") or 0
            cat = d.get("dominant_category") or ""
            intent = rrel.get("intent_relevance")
            if intent is not None:
                intent_sum += intent
                intent_n += 1
            if VERDICT_RANK.get(v, 0) > best_verdict_rank:
                best_verdict_rank = VERDICT_RANK[v]
                best_verdict_label = v
            best_vibe = max(best_vibe, vr)
            worst_vibe = min(worst_vibe, vr)
            if cat:
                categories[cat] += 1
            member_rows.append({
                "keyword": m,
                "verdict": v,
                "vibe_roi": round(vr, 2),
                "payback_months": d.get("payback_months"),
                "ltv": d.get("ltv"),
                "demand_level": d.get("demand_level"),
                "supply_level": d.get("supply_level"),
                "concentration_index": d.get("concentration_index"),
                "intent_relevance": intent,
                "dominant_category": cat,
            })

        dominant_cat = max(categories, key=categories.get) if categories else ""
        avg_intent = round(intent_sum / intent_n, 2) if intent_n else None

        member_rows.sort(key=lambda x: -(x["vibe_roi"] or 0))
        cluster_id = theme_token

        clusters.append({
            "id": cluster_id,
            "theme_tokens": sorted(theme),
            "size": len(members),
            "unique_relevant_apps": len(unique_apps),
            "unique_total_ratings": unique_total_ratings,
            "best_verdict": best_verdict_label,
            "best_verdict_rank": best_verdict_rank,
            "best_vibe_roi": round(best_vibe, 2),
            "worst_vibe_roi": round(worst_vibe, 2) if worst_vibe < 999 else 0,
            "avg_intent_relevance": avg_intent,
            "dominant_category": dominant_cat,
            "members": member_rows,
            "top_apps": unique_apps[:10],
        })

    # Sort: clusters with better verdict + more members first
    clusters.sort(key=lambda c: (-c["best_verdict_rank"], -c["best_vibe_roi"], -c["size"]))

    with open(OUT_PATH, "w") as f:
        json.dump(clusters, f, indent=2)

    print(f"Saved {len(clusters)} clusters → {OUT_PATH}")

    # Preview
    print("\nTop 10 multi-member clusters by best vibe_roi:")
    multi = [c for c in clusters if c["size"] > 1]
    multi.sort(key=lambda c: -c["best_vibe_roi"])
    for c in multi[:10]:
        mbrs = ", ".join(m["keyword"] for m in c["members"][:4])
        more = f" +{c['size']-4}" if c["size"] > 4 else ""
        print(f"  size={c['size']:2}  best={c['best_vibe_roi']:<5}  "
              f"verdict={c['best_verdict']:17}  apps={c['unique_relevant_apps']:<3}  "
              f"[{c['id']}]  → {mbrs}{more}")

    print("\nExamples matching user hints:")
    for theme in ("baby", "sleep", "noise"):
        c = next((c for c in clusters if c["id"] == theme), None)
        if c:
            mbrs = ", ".join(m["keyword"] for m in c["members"][:8])
            more = f" +{c['size']-8}" if c["size"] > 8 else ""
            print(f"  [{c['id']}] size={c['size']} → {mbrs}{more}")


if __name__ == "__main__":
    main()
