"""Build per-case feature vectors for the MAS-conditioned stacker.

For each case in a split, produce a ~30-dim feature vector by joining:
  - TF-IDF + LR calibrated probabilities (12 dims, one per parent class)
  - DtV diagnostician top-5 ranked confidences (5 dims, padded with zeros)
  - DtV criterion-checker met_ratio per target disorder (12 dims — the 12
    paper classes; values in [0, 2], aligned to PAPER_12_CLASSES order)
  - TF-IDF top1 margin (top1_prob - top2_prob), a scalar gating signal
    shown in the pre-rebase analysis to correlate with DtV's relative value
  - DtV abstain flag (1 if checker coverage < 50% or diagnostician failed,
    else 0)

Output schema:
    {
      "case_id": str,
      "gold_parents": list[str],              # multi-label targets in paper-12
      "features": list[float],                # 31 floats, feature order fixed
      "feature_names": list[str],             # same length as features
      "tfidf_primary": str,                   # for audit
      "dtv_primary": str,                     # for audit
    }

Usage:
    uv run python scripts/stacker/build_features.py \\
        --tfidf-pred outputs/tfidf_baseline/<split>/predictions.jsonl \\
        --dtv-pred   results/rebase_v2.5/<dtv_run>/predictions.jsonl \\
        --eval-split <dev_hpo|test_final> \\
        --out        outputs/stacker_features/<split>/features.jsonl

The script refuses to join splits that weren't eval'd on the same case-id
set. Mismatch triggers a clear error with the diff.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from culturedx.eval.lingxidiag_paper import PAPER_12_CLASSES, gold_to_parent_list  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Feature-name schema (fixed order)
# --------------------------------------------------------------------------- #
def feature_names() -> list[str]:
    """The fixed feature order. Any changes here require retraining the stacker."""
    names: list[str] = []
    # Block 1: TF-IDF class probabilities (12 dims)
    names.extend(f"tfidf_p__{c}" for c in PAPER_12_CLASSES)
    # Block 2: DtV diagnostician top-5 ranked confidences (5 dims)
    names.extend(f"dtv_rank{i + 1}_conf" for i in range(5))
    # Block 3: DtV criterion checker met_ratio per paper-12 class (12 dims)
    names.extend(f"dtv_checker_mr__{c}" for c in PAPER_12_CLASSES)
    # Block 4: gating scalars
    names.append("tfidf_top1_margin")
    names.append("dtv_abstain_flag")
    return names


FEATURE_NAMES = feature_names()
N_FEATURES = len(FEATURE_NAMES)  # 31


def _parent_of(code: str | None) -> str | None:
    if code is None:
        return None
    s = str(code).strip().upper()
    if not s:
        return None
    return s.split(".")[0]


def _tfidf_prob_vector(record: dict) -> list[float]:
    """Pull 12-dim calibrated probability vector from a TF-IDF prediction.

    Expected record format (from scripts/train_tfidf_baseline.py):
        {
          "ranked_codes":  [...],    # length 12, values in PAPER_12_CLASSES
          "proba_scores":  [...],    # length 12, aligned to ranked_codes
        }
    """
    codes = record.get("ranked_codes") or []
    scores = record.get("proba_scores") or []
    prob = {c: 0.0 for c in PAPER_12_CLASSES}
    for c, s in zip(codes, scores):
        if c in prob:
            prob[c] = float(s)
    return [prob[c] for c in PAPER_12_CLASSES]


def _dtv_top5_conf(record: dict) -> list[float]:
    """Pull DtV diagnostician top-5 ranked confidences.

    The DtV runner emits a `decision_trace` per case. We look in a few known
    places for the ranked confidences and fall back to zeros.
    """
    trace = record.get("decision_trace") or {}
    # Several historic shapes — try them in order:
    for key in ("diagnostician_ranked", "ranked_codes_with_conf",
                "diagnostician_top_k", "ranking"):
        ranked = trace.get(key)
        if ranked:
            confs = []
            for item in ranked[:5]:
                if isinstance(item, dict):
                    confs.append(float(item.get("confidence") or item.get("score") or 0.0))
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    confs.append(float(item[1]))
                else:
                    confs.append(0.0)
            return confs + [0.0] * (5 - len(confs))

    # Fallback: use ranked_codes if present and assume uniform confidence
    codes = record.get("ranked_codes") or []
    confs = [0.5 if c else 0.0 for c in codes[:5]]
    return confs + [0.0] * (5 - len(confs))


def _dtv_checker_mr(record: dict) -> list[float]:
    """Pull per-disorder met_ratio from the DtV criterion checker.

    The record's `decision_trace.raw_checker_outputs` contains one entry
    per disorder that was checked. Each entry has a `met_ratio` field
    (met criteria / minimum threshold).
    """
    trace = record.get("decision_trace") or {}
    raw = trace.get("raw_checker_outputs") or []
    mr = {c: 0.0 for c in PAPER_12_CLASSES}
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        disorder = entry.get("disorder_code") or entry.get("code") or ""
        parent = _parent_of(disorder)
        if parent in mr:
            ratio = entry.get("met_ratio")
            if ratio is None:
                # Fallback: met/required
                met = entry.get("met_count") or 0
                req = entry.get("required_count") or 1
                ratio = met / max(req, 1)
            # Only overwrite if we haven't seen a larger ratio for this parent
            mr[parent] = max(mr[parent], float(ratio))
    return [mr[c] for c in PAPER_12_CLASSES]


def _tfidf_top1_margin(record: dict) -> float:
    scores = record.get("proba_scores") or []
    if len(scores) >= 2:
        return float(scores[0]) - float(scores[1])
    return 0.0


def _dtv_abstain_flag(record: dict) -> float:
    """1.0 if DtV effectively abstained (no checker output, or explicit abstain)."""
    if record.get("decision") == "abstain":
        return 1.0
    trace = record.get("decision_trace") or {}
    raw = trace.get("raw_checker_outputs") or []
    if not raw:
        return 1.0
    if record.get("primary_diagnosis") in (None, "", "UNKNOWN"):
        return 1.0
    return 0.0


def build_features(tfidf_rec: dict, dtv_rec: dict) -> list[float]:
    feats = []
    feats.extend(_tfidf_prob_vector(tfidf_rec))
    feats.extend(_dtv_top5_conf(dtv_rec))
    feats.extend(_dtv_checker_mr(dtv_rec))
    feats.append(_tfidf_top1_margin(tfidf_rec))
    feats.append(_dtv_abstain_flag(dtv_rec))
    assert len(feats) == N_FEATURES, f"feature length mismatch: {len(feats)} vs {N_FEATURES}"
    return feats


# --------------------------------------------------------------------------- #
# I/O
# --------------------------------------------------------------------------- #
def _load_jsonl(path: Path) -> dict[str, dict]:
    if not path.exists():
        raise FileNotFoundError(f"{path} not found")
    out = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            cid = str(rec.get("case_id", ""))
            if not cid:
                continue
            out[cid] = rec
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tfidf-pred", type=Path, required=True,
                        help="Path to TF-IDF predictions.jsonl")
    parser.add_argument("--dtv-pred", type=Path, required=True,
                        help="Path to DtV predictions.jsonl (must be on the same split)")
    parser.add_argument("--eval-split", required=True,
                        choices=["dev_hpo", "test_final"],
                        help="Which logical split these predictions are on")
    parser.add_argument("--out", type=Path, required=True,
                        help="Output JSONL path")
    parser.add_argument("--allow-missing-dtv", action="store_true",
                        help="Proceed even if DtV is missing some cases "
                             "(fills their DtV features with zeros + abstain flag=1)")
    args = parser.parse_args()

    logger.info("Loading TF-IDF predictions: %s", args.tfidf_pred)
    tfidf_map = _load_jsonl(args.tfidf_pred)
    logger.info("  %d TF-IDF records", len(tfidf_map))

    logger.info("Loading DtV predictions: %s", args.dtv_pred)
    dtv_map = _load_jsonl(args.dtv_pred)
    logger.info("  %d DtV records", len(dtv_map))

    tfidf_ids = set(tfidf_map)
    dtv_ids = set(dtv_map)
    missing_dtv = tfidf_ids - dtv_ids
    missing_tfidf = dtv_ids - tfidf_ids
    if missing_tfidf:
        logger.warning(
            "%d case ids in DtV but not TF-IDF. First 5: %s. These will be skipped.",
            len(missing_tfidf), list(missing_tfidf)[:5],
        )
    if missing_dtv and not args.allow_missing_dtv:
        raise RuntimeError(
            f"{len(missing_dtv)} case ids in TF-IDF but not DtV. "
            f"First 5: {list(missing_dtv)[:5]}. "
            f"Re-run DtV on the full {args.eval_split} split, or pass "
            f"--allow-missing-dtv to fill with zeros."
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    n_written = 0
    n_missing_dtv = 0
    with args.out.open("w", encoding="utf-8") as f:
        for cid, tfidf_rec in tfidf_map.items():
            dtv_rec = dtv_map.get(cid)
            if dtv_rec is None:
                if not args.allow_missing_dtv:
                    continue
                # Synthetic abstain
                dtv_rec = {"case_id": cid, "decision": "abstain"}
                n_missing_dtv += 1

            feats = build_features(tfidf_rec, dtv_rec)
            gold = tfidf_rec.get("gold_diagnoses") or []
            # Normalize gold to paper-12 parents
            gold_parents = []
            for g in gold:
                p = _parent_of(str(g))
                if not p:
                    continue
                if p in PAPER_12_CLASSES:
                    gold_parents.append(p)
                else:
                    # Fallback: use gold_to_parent_list to resolve "Others" etc.
                    for q in gold_to_parent_list(str(g)):
                        gold_parents.append(q)

            rec = {
                "case_id": cid,
                "eval_split": args.eval_split,
                "gold_parents": list(dict.fromkeys(gold_parents)),  # dedup, keep order
                "features": feats,
                "feature_names": FEATURE_NAMES,
                "tfidf_primary": tfidf_rec.get("primary_diagnosis"),
                "dtv_primary": dtv_rec.get("primary_diagnosis"),
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n_written += 1

    logger.info("Wrote %d feature records to %s", n_written, args.out)
    if n_missing_dtv:
        logger.warning("%d cases had missing DtV (filled with abstain features)",
                       n_missing_dtv)


if __name__ == "__main__":
    main()
