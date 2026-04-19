#!/usr/bin/env python3
"""Group the 1000 keywords into theme clusters.

Two levels of grouping:

1. Primary split: `<theme_token> · <dominant_category>`. A theme token is a
   non-generic domain token with document frequency in [MIN_DF, MAX_DF].
   We split by category so "health" doesn't merge battery-health (Utilities)
   with pet-health (Health & Fitness). A (token, category) bucket becomes
   a cluster only if it has >= MIN_CLUSTER_SIZE members.

2. Inside each primary cluster, we look for sub-groups of >= MIN_SUBGROUP
   members that share a second distinctive token. E.g. inside `#car`, we
   surface `+insurance` (car insurance compare, car value estimator...),
   `+rental` (car rental compare...), `+maintenance` (car maintenance
   tracker, car wash finder...). This gives the user the nested "close
   topics" view inside a large cluster.

Keywords with no qualifying primary bucket go to `(unclustered)`.

Output: clusters.json (consumed by /api/clusters).
"""

import json
import os
import sys
from collections import defaultdict
from itertools import combinations

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from relevance_rescore import domain_tokens

DEEP_PATH = os.path.join(ROOT, "deep_research.json")
REL_PATH = os.path.join(ROOT, "relevance_rescored.json")
OUT_PATH = os.path.join(ROOT, "clusters.json")

# A theme token must appear in [MIN_DF, MAX_DF] keywords.
MIN_DF = 2
MAX_DF = 25
# A primary (token, category) bucket is kept only if it has >= this many members.
# Kept at 2 because splitting by category already narrows the theme a lot, and
# a 2-keyword pair inside one category still represents a coherent mini-niche
# (e.g. `health · H&F` = goat + cat health trackers — same pet-care intent).
MIN_CLUSTER_SIZE = 2
# A secondary-token subgroup inside a primary cluster is surfaced only if >= this many members.
MIN_SUBGROUP = 3
# A bigram theme (unordered pair of tokens) is kept if it co-occurs in >= this
# many keywords. Set low because bigrams are naturally rarer and more specific:
# "car+rental" in 1 kw is already a narrow intent; pairs that appear in 2+
# keywords are the sweet spot.
BIGRAM_MIN_DF = 2


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


def gini(values: list[int]) -> float:
    """Standard Gini coefficient on non-negative values.

    0 = perfectly equal (all apps share ratings evenly), 1 = all ratings on
    one app. Returns None-equivalent 0.0 for empty / single-item / all-zero
    lists so it's always comparable as a float.
    """
    xs = sorted(v for v in values if v is not None)
    n = len(xs)
    total = sum(xs)
    if n < 2 or total <= 0:
        return 0.0
    weighted = sum((i + 1) * x for i, x in enumerate(xs))
    return (2 * weighted) / (n * total) - (n + 1) / n


def primary_buckets(
    token_by_kw: dict[str, set],
    category_by_kw: dict[str, str],
) -> list[tuple[str, str, list[str]]]:
    """Return (theme_token, category, members) tuples — one per primary cluster.

    A bucket is emitted only if it has >= MIN_CLUSTER_SIZE members.
    """
    tok_idx: dict[str, list[str]] = defaultdict(list)
    for kw, toks in token_by_kw.items():
        for t in toks:
            tok_idx[t].append(kw)

    emitted: list[tuple[str, str, list[str]]] = []
    for tok, kws in tok_idx.items():
        if len(kws) < MIN_DF or len(kws) > MAX_DF:
            continue
        by_cat: dict[str, list[str]] = defaultdict(list)
        for kw in kws:
            cat = category_by_kw.get(kw) or "—"
            by_cat[cat].append(kw)

        leftover: list[str] = []
        for cat, members in by_cat.items():
            if len(members) >= MIN_CLUSTER_SIZE:
                emitted.append((tok, cat, sorted(set(members))))
            else:
                leftover.extend(members)

        # If a token has members that didn't fit into any per-category cluster
        # (e.g. `speed` has 1 keyword in each of 5 different categories), keep
        # them together in a `<token> · (mixed)` cluster so they're not lost.
        if len(leftover) >= MIN_CLUSTER_SIZE:
            emitted.append((tok, "(mixed)", sorted(set(leftover))))
    return emitted


def bigram_buckets(token_by_kw: dict[str, set]) -> list[tuple[list[str], list[str]]]:
    """Return (theme_tokens, members) pairs — one per bigram cluster.

    A bigram is an unordered pair of two domain tokens that co-occur in the
    same keyword. We emit any bigram that appears in >= BIGRAM_MIN_DF
    keywords. No category split: bigrams are already narrow, so splitting
    by category tends to leave 1-keyword fragments.
    """
    bigram_idx: dict[tuple[str, str], set[str]] = defaultdict(set)
    for kw, toks in token_by_kw.items():
        tokens = sorted(toks)
        for a, b in combinations(tokens, 2):
            bigram_idx[(a, b)].add(kw)

    emitted: list[tuple[list[str], list[str]]] = []
    for (a, b), kws in bigram_idx.items():
        if len(kws) >= BIGRAM_MIN_DF:
            emitted.append(([a, b], sorted(kws)))
    return emitted


def find_subgroups(
    members: list[str],
    token_by_kw: dict[str, set],
    primary_tokens: list[str],
) -> tuple[list[dict], list[str]]:
    """Inside a primary cluster, split members into sub-groups of >=
    MIN_SUBGROUP that share a further distinctive token (not in the
    cluster's primary tokens).

    Returns (subgroups, orphans) where each subgroup is
    {token: str, members: [str]} and orphans are members that didn't fit.
    Greedy: pick the largest subgroup first; each member assigned once.
    """
    primary_set = set(primary_tokens)
    sub_idx: dict[str, list[str]] = defaultdict(list)
    for m in members:
        for t in token_by_kw.get(m, set()):
            if t in primary_set:
                continue
            sub_idx[t].append(m)

    subgroups: list[dict] = []
    assigned: set[str] = set()
    candidates = sorted(sub_idx.items(), key=lambda x: (-len(x[1]), len(x[0])))
    for tok, kws in candidates:
        free = [k for k in kws if k not in assigned]
        if len(free) >= MIN_SUBGROUP:
            subgroups.append({"token": tok, "members": sorted(free)})
            assigned.update(free)

    orphans = sorted(m for m in members if m not in assigned)
    return subgroups, orphans


def build_cluster(
    theme_tokens: list[str],
    category: str,
    members: list[str],
    deep_by_norm: dict,
    rel_by_norm: dict,
    token_by_kw: dict[str, set],
) -> dict:
    # Aggregate relevant apps across all members, dedupe by (name, developer)
    seen_apps: dict[tuple, dict] = {}
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
    rating_gini = round(gini([a["rating_count"] for a in unique_apps]), 3)
    top_app_share = (
        round(unique_apps[0]["rating_count"] / unique_total_ratings, 3)
        if unique_apps and unique_total_ratings > 0 else 0.0
    )

    member_rows: list[dict] = []
    intent_sum, intent_n = 0.0, 0
    best_verdict_rank, best_verdict_label = 0, "AVOID"
    best_vibe, worst_vibe = 0.0, 999.0

    for m in members:
        d = deep_by_norm.get(m) or {}
        rrel = rel_by_norm.get(m) or {}
        v = verdict_for(d)
        vr = d.get("vibe_roi") or 0
        intent = rrel.get("intent_relevance")
        if intent is not None:
            intent_sum += intent
            intent_n += 1
        if VERDICT_RANK.get(v, 0) > best_verdict_rank:
            best_verdict_rank = VERDICT_RANK[v]
            best_verdict_label = v
        best_vibe = max(best_vibe, vr)
        worst_vibe = min(worst_vibe, vr)
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
            "dominant_category": d.get("dominant_category") or "",
        })

    avg_intent = round(intent_sum / intent_n, 2) if intent_n else None
    member_rows.sort(key=lambda x: -(x["vibe_roi"] or 0))

    # Secondary subgroups
    subgroups, orphans = find_subgroups(members, token_by_kw, theme_tokens)
    # Project subgroups into the member_rows form (keep ordering by vibe_roi)
    row_by_kw = {r["keyword"]: r for r in member_rows}
    sub_blocks = []
    for sg in subgroups:
        rows = sorted(
            (row_by_kw[k] for k in sg["members"] if k in row_by_kw),
            key=lambda r: -(r["vibe_roi"] or 0),
        )
        best = max((VERDICT_RANK.get(r["verdict"], 0) for r in rows), default=0)
        sub_blocks.append({
            "token": sg["token"],
            "size": len(rows),
            "best_verdict_rank": best,
            "members": rows,
        })
    sub_blocks.sort(key=lambda b: (-b["best_verdict_rank"], -b["size"]))
    orphan_rows = sorted(
        (row_by_kw[k] for k in orphans if k in row_by_kw),
        key=lambda r: -(r["vibe_roi"] or 0),
    )

    theme_label = " + ".join(theme_tokens) if theme_tokens else ""
    if theme_label and category:
        cluster_id = f"{theme_label}·{category}"
    else:
        cluster_id = theme_label or category or "(unclustered)"

    return {
        "id": cluster_id,
        "theme_tokens": theme_tokens,
        "theme_token": theme_tokens[0] if theme_tokens else "",
        "theme_length": len(theme_tokens),
        "category": category,
        "size": len(members),
        "unique_relevant_apps": len(unique_apps),
        "unique_total_ratings": unique_total_ratings,
        "rating_gini": rating_gini,
        "top_app_share": top_app_share,
        "best_verdict": best_verdict_label,
        "best_verdict_rank": best_verdict_rank,
        "best_vibe_roi": round(best_vibe, 2),
        "worst_vibe_roi": round(worst_vibe, 2) if worst_vibe < 999 else 0,
        "avg_intent_relevance": avg_intent,
        "members": member_rows,
        "subgroups": sub_blocks,
        "orphans": orphan_rows,
        "top_apps": unique_apps[:10],
    }


def main():
    with open(DEEP_PATH) as f:
        deep = json.load(f)
    with open(REL_PATH) as f:
        rel = json.load(f)

    deep_by_norm = {r["keyword_normalized"]: r for r in deep}
    rel_by_norm = {r["keyword_normalized"]: r for r in rel}

    token_by_kw: dict[str, set] = {}
    category_by_kw: dict[str, str] = {}
    for r in rel:
        norm = r.get("keyword_normalized")
        if not norm or "error" in r:
            continue
        toks = set(r.get("domain_tokens") or domain_tokens(norm))
        token_by_kw[norm] = toks
        category_by_kw[norm] = (deep_by_norm.get(norm) or {}).get("dominant_category") or "—"

    # 1-word clusters (token · category, with category split)
    buckets = primary_buckets(token_by_kw, category_by_kw)
    clusters_1w = [
        build_cluster([tok], cat, members, deep_by_norm, rel_by_norm, token_by_kw)
        for tok, cat, members in buckets
    ]
    covered_1w = {m for _, _, ms in buckets for m in ms}
    singletons = sorted(k for k in token_by_kw if k not in covered_1w)
    if singletons:
        clusters_1w.append(build_cluster(
            [], "(unclustered)", singletons,
            deep_by_norm, rel_by_norm, token_by_kw,
        ))

    # 2-word clusters (bigram theme, no category split)
    bg = bigram_buckets(token_by_kw)
    clusters_2w = [
        build_cluster(tokens, "", members, deep_by_norm, rel_by_norm, token_by_kw)
        for tokens, members in bg
    ]
    covered_2w = {m for _, ms in bg for m in ms}
    singletons_2w = sorted(k for k in token_by_kw if k not in covered_2w)
    if singletons_2w:
        clusters_2w.append(build_cluster(
            [], "(unclustered)", singletons_2w,
            deep_by_norm, rel_by_norm, token_by_kw,
        ))

    clusters = clusters_1w + clusters_2w
    print(f"Built {len(clusters_1w)} one-word and {len(clusters_2w)} two-word clusters "
          f"(from {len(token_by_kw)} keywords).")

    clusters.sort(key=lambda c: (-c["theme_length"], -c["best_verdict_rank"],
                                  -c["best_vibe_roi"], -c["size"]))

    with open(OUT_PATH, "w") as f:
        json.dump(clusters, f, indent=2)

    print(f"Saved {len(clusters)} clusters → {OUT_PATH}")

    print("\nTop 10 two-word clusters by best vibe_roi:")
    multi = [c for c in clusters if c["theme_length"] == 2]
    multi.sort(key=lambda c: -c["best_vibe_roi"])
    for c in multi[:10]:
        subs = ", ".join(f"+{s['token']}({s['size']})" for s in c["subgroups"])
        print(f"  [{c['id']:40}] size={c['size']:2} best={c['best_vibe_roi']:<5} "
              f"verdict={c['best_verdict']:17} subs=[{subs}]")

    print("\nSpot checks (2-word):")
    for target in ("car + rental", "car + wash", "car + insurance", "car + compare",
                   "baby + sleep", "baby + food", "baby + milestone",
                   "noise + white", "noise + sleep", "health + battery", "health + cat"):
        c = next((c for c in clusters
                  if c["theme_length"] == 2
                  and sorted(c["theme_tokens"]) == sorted(target.split(" + "))), None)
        if c:
            kws = ", ".join(m["keyword"] for m in c["members"])
            print(f"  [{c['id']}] size={c['size']} → {kws}")
        else:
            print(f"  [{target}] — no bigram cluster (below MIN_DF={BIGRAM_MIN_DF})")


if __name__ == "__main__":
    main()
