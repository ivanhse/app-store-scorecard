#!/usr/bin/env python3
"""Re-apply classifier + vibe-ROI scoring to cached signals (no new API calls)."""

import json
import sys

sys.path.insert(0, ".")
from deep_research import classify, compute_vibe_roi, normalize_keyword, enrich  # noqa

BATCH_PATH = "/Users/ivansamsurin/Documents/myprojects/app-store-scorecard/batch_results.json"
CACHE_PATH = "/Users/ivansamsurin/Documents/myprojects/app-store-scorecard/deep_research_cache.json"
OUT_PATH = "/Users/ivansamsurin/Documents/myprojects/app-store-scorecard/deep_research.json"


def main():
    with open(BATCH_PATH) as f:
        batch = json.load(f)
    with open(CACHE_PATH) as f:
        cache = json.load(f)

    # Re-derive incumbent (word-boundary) from cached top10_names.
    # If cache was produced with old substring match, recompute.
    import re
    from deep_research import DOMINANT_INCUMBENTS

    def recompute_incumbent(top3):
        for a in top3:
            name = (a.get("name") or "").lower()
            tokens = set(t for t in re.split(r"[^a-z0-9+]+", name) if t)
            for dom in DOMINANT_INCUMBENTS:
                dom_tokens = dom.split()
                if all(t in tokens for t in dom_tokens):
                    return dom
        return None

    results = []
    for row in batch:
        original = row["keyword"]
        normed = normalize_keyword(original)
        signals = cache.get(normed, {})
        if "error" in signals or not signals:
            results.append({
                "keyword_original": original,
                "keyword_normalized": normed,
                "error": signals.get("error", "missing cache"),
            })
            continue

        # Recompute incumbent with stricter matcher
        signals["incumbent"] = recompute_incumbent(signals.get("top3", []))

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

    results.sort(key=lambda r: r.get("vibe_roi", -1), reverse=True)

    with open(OUT_PATH, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Re-ranked {len(results)} rows → {OUT_PATH}")
    print("\nTop 30 by vibe_roi:")
    for r in results[:30]:
        kws = ",".join(r.get("wins", []))
        kls = ",".join(r.get("kills", []))
        print(f"  {r.get('vibe_roi', 0):>6.2f} | pb={r.get('payback_months', 0):>5.1f}mo | "
              f"cat={r.get('dominant_category','?')[:12]:12} | "
              f"{r['keyword_normalized'][:38]:38} | wins[{kws}] kills[{kls}]")


if __name__ == "__main__":
    main()
