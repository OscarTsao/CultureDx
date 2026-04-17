"""Reciprocal Rank Fusion (RRF) ensemble for CultureDx predictions.

CPU-only post-hoc fusion of ranked code lists from multiple diagnostic systems.
Reference: Cormack, Clarke & Butt (2009) – Reciprocal Rank Fusion.
"""
from __future__ import annotations

import json
from pathlib import Path


def rrf_fuse(
    ranked_lists: list[list[str]],
    weights: list[float] | None = None,
    k: int = 60,
) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion on multiple ranked code lists.

    For each code across all lists:
      score += weight_i / (k + rank_i)
    where rank_i is 1-indexed position in list i (or skipped if absent).

    Returns (code, score) pairs sorted by descending fused score.
    """
    n = len(ranked_lists)
    if weights is None:
        weights = [1.0] * n
    if len(weights) != n:
        raise ValueError(f"weights length {len(weights)} != ranked_lists length {n}")

    scores: dict[str, float] = {}
    for i, rlist in enumerate(ranked_lists):
        w = weights[i]
        for rank_0, code in enumerate(rlist):
            rank_1 = rank_0 + 1  # 1-indexed
            scores[code] = scores.get(code, 0.0) + w / (k + rank_1)

    # Sort by descending score, then alphabetically for ties
    sorted_codes = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    return sorted_codes


def ensemble_predictions(
    pred_paths: list[str],
    weights: list[float] | None = None,
    k: int = 60,
    max_labels: int = 2,
) -> list[dict]:
    """Load multiple predictions.jsonl files, fuse per case_id using RRF.

    For each case (by case_id intersection):
    - Build ranked list from each system: [primary] + comorbid_diagnoses
    - Apply rrf_fuse
    - Output: primary = top-1 fused, comorbid = [top-2..] if score ratio > 0.5

    Returns list of prediction dicts with same schema as input.
    """
    # Load all prediction sets
    all_preds: list[dict[str, dict]] = []
    for path_str in pred_paths:
        path = Path(path_str)
        case_map: dict[str, dict] = {}
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                cid = rec.get("case_id", "")
                if cid:
                    case_map[cid] = rec
        all_preds.append(case_map)

    # Find intersection of case_ids
    common_ids = set(all_preds[0].keys())
    for pmap in all_preds[1:]:
        common_ids &= set(pmap.keys())

    # Use first system's records as base template (for gold_diagnoses etc.)
    results: list[dict] = []
    for cid in sorted(common_ids):
        # Build ranked list per system: [primary] + comorbid
        ranked_lists: list[list[str]] = []
        for pmap in all_preds:
            rec = pmap[cid]
            codes: list[str] = []
            primary = rec.get("primary_diagnosis", "")
            if primary:
                codes.append(primary)
            for c in rec.get("comorbid_diagnoses", []):
                if c and c not in codes:
                    codes.append(c)
            ranked_lists.append(codes)

        # Fuse
        fused = rrf_fuse(ranked_lists, weights=weights, k=k)
        if not fused:
            continue

        top_code, top_score = fused[0]

        # Select comorbid: codes whose score ratio vs top > 0.5
        comorbid: list[str] = []
        for code, score in fused[1:]:
            if top_score > 0 and (score / top_score) > 0.5:
                comorbid.append(code)
            if len(comorbid) >= max_labels - 1:
                break

        # Build output from first system's template
        base = all_preds[0][cid]
        out = {
            "schema_version": base.get("schema_version", "v1"),
            "run_id": "t2_rrf",
            "case_id": cid,
            "order_index": base.get("order_index", 0),
            "dataset": base.get("dataset", "lingxidiag16k"),
            "gold_diagnoses": base.get("gold_diagnoses", []),
            "primary_diagnosis": top_code,
            "comorbid_diagnoses": comorbid,
            "confidence": round(top_score, 6),
            "decision": "diagnosis",
            "mode": "ensemble_rrf",
            "model_name": "rrf_ensemble",
            "prompt_hash": "",
            "language_used": base.get("language_used", "zh"),
            "routing_mode": "ensemble",
            "scope_policy": base.get("scope_policy", ""),
            "candidate_disorders": base.get("candidate_disorders", []),
            "decision_trace": {
                "ensemble_method": "rrf",
                "k": k,
                "weights": weights,
                "fused_ranking": [(c, round(s, 6)) for c, s in fused[:5]],
                "systems": [str(p) for p in pred_paths],
            },
            "stage_timings": {},
            "failures": [],
        }
        results.append(out)

    return results


__all__ = ["rrf_fuse", "ensemble_predictions"]
