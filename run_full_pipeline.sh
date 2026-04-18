#!/bin/bash
# Re-run the full data pipeline after batch_results.json has new keywords.
# Each stage uses caches so only new keywords hit iTunes.
set -e
cd "$(dirname "$0")"

echo "==> deep_research.py (enrich new kws, cache-aware)"
python3 deep_research.py

echo "==> relevance_rescore.py (score top-10 against intent)"
python3 relevance_rescore.py

echo "==> apply_relevance_to_deep_research.py (merge intent into deep_research.json)"
python3 apply_relevance_to_deep_research.py

echo "==> build_clusters.py (rebuild clusters.json)"
python3 build_clusters.py

echo "==> done."
