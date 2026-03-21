# Ranking Improvement Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve top-1 diagnostic accuracy from 42.5-53.0% by fixing the ranking bottleneck (40% of errors are detection-correct but ranking-wrong).

**Architecture:** Six interventions ordered by ROI: (1) evidence pipeline at scale, (2) learned ranker replacing fixed-weight calibrator, (3) contrastive failure analysis, (4) temporal criterion enhancement, (5) cross-lingual validation, (6) mode ensemble. Each is independently testable and deployable.

**Tech Stack:** Python 3.12, scikit-learn (LogisticRegression), vLLM (Qwen3-32B-AWQ), BGE-M3 (CPU), existing CultureDx pipeline.

---

## Chunk 1: Evidence Pipeline at Scale + Mode Ensemble

### Task 1: Run Evidence Pipeline N=200 on LingxiDiag

**Context:** Evidence pipeline (BGE-M3 retriever + somatization) was only tested at N=50. All N=200 results are `no_evidence`. Evidence directly affects calibrator ranking via `evidence_coverage` weight (0.207, tied for second-largest with avg_confidence and threshold_ratio; core_score=0.30 is largest). BGE-M3 runs on CPU (no GPU conflict with vLLM).

**Files:**
- Run: `scripts/ablation_sweep.py` (no changes needed)
- Output: `outputs/sweeps/evidence_lingxidiag_*/`

**Prerequisites:** Start vLLM server on GPU.

- [ ] **Step 1: Start vLLM server**

```bash
nohup python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen3-32B-AWQ \
    --port 8000 \
    --enable-prefix-caching \
    --max-model-len 8192 \
    --gpu-memory-utilization 0.92 \
    > outputs/vllm_server_ranking.log 2>&1 &
echo $! > outputs/vllm_pid.txt
```

Wait for server healthy: `curl -s http://localhost:8000/health`

- [ ] **Step 2: Run evidence ablation on LingxiDiag (3 conditions)**

```bash
nohup uv run python scripts/ablation_sweep.py \
    --provider vllm --model Qwen/Qwen3-32B-AWQ \
    --modes hied --evidence-ablation --retriever bge-m3 \
    -n 200 --seed 42 --dataset lingxidiag16k \
    --sweep-name evidence_lingxidiag \
    > outputs/launch_evidence_lingxidiag.log 2>&1 &
echo $! > outputs/evidence_lingxidiag_pid.txt
```

This runs 3 conditions:
1. `hied_no_evidence` (baseline, should match prior results ~42.5%)
2. `hied_bge-m3_evidence` (evidence + somatization ON)
3. `hied_bge-m3_no_somatization` (evidence only, no somatization)

**Expected time:** ~200 cases × 3 conditions × ~25s/case = ~4.2 hours

- [ ] **Step 3: Verify results**

```bash
python3 -c "
import json
from pathlib import Path
for d in sorted(Path('outputs/sweeps').glob('evidence_lingxidiag_*/*/')):
    m = d / 'metrics.json'
    if m.exists():
        data = json.load(open(m))
        mn = data.get('metrics_parent_normalized', {})
        print(f'{d.name}: top1={mn.get(\"top1_accuracy\",\"?\")} top3={mn.get(\"top3_accuracy\",\"?\")}')
"
```

Expected: evidence conditions show +3-5pp over no_evidence baseline.

### Task 2: Run Evidence Pipeline N=200 on MDD-5k

**Files:**
- Run: `scripts/ablation_sweep.py`
- Output: `outputs/sweeps/evidence_mdd5k_*/`

- [ ] **Step 1: Run evidence ablation on MDD-5k (3 conditions)**

```bash
nohup uv run python scripts/ablation_sweep.py \
    --provider vllm --model Qwen/Qwen3-32B-AWQ \
    --modes hied --evidence-ablation --retriever bge-m3 \
    -n 200 --seed 42 --dataset mdd5k_raw \
    --sweep-name evidence_mdd5k \
    > outputs/launch_evidence_mdd5k.log 2>&1 &
echo $! > outputs/evidence_mdd5k_pid.txt
```

**Expected time:** ~200 cases × 3 conditions × ~70s/case = ~11.7 hours

- [ ] **Step 2: Run comorbidity analysis on evidence results**

```bash
uv run python scripts/analyze_comorbidity.py \
    --sweep-dirs outputs/sweeps/evidence_lingxidiag_* outputs/sweeps/evidence_mdd5k_* \
    --four-class --save
```

- [ ] **Step 3: Commit results**

```bash
git add outputs/sweeps/evidence_* outputs/launch_evidence_*.log
git commit -m "data: evidence pipeline N=200 results (LingxiDiag + MDD-5k)"
```

### Task 3: Build confidence-weighted mode ensemble

**Context:** Zero-cost improvement from existing N=200 predictions. Bootstrap showed HiED+Single ensemble at 55.5% on MDD-5k. Uses predictions from `v10_lingxidiag`, `v10_mdd5k`, `n200_3mode`.

**Files:**
- Create: `scripts/ensemble_predict.py` (~80 lines)
- Test: Manual validation against existing metrics

- [ ] **Step 1: Write ensemble script**

```python
#!/usr/bin/env python3
"""Confidence-weighted mode ensemble from existing predictions.

Usage:
    uv run python scripts/ensemble_predict.py \
        --sweep-dir outputs/sweeps/n200_3mode_20260320_131920 \
        --modes hied_no_evidence,psycot_no_evidence,single_no_evidence \
        --weights 1.0,0.9,0.8
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from culturedx.eval.metrics import compute_diagnosis_metrics, normalize_code_list


def ensemble_predict(
    predictions_by_mode: dict[str, list[dict]],
    weights: dict[str, float],
) -> list[dict]:
    """Weighted vote ensemble: highest weighted confidence wins."""
    # Index by case_id
    by_case: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for mode_name, preds in predictions_by_mode.items():
        for p in preds:
            by_case[p["case_id"]].append((mode_name, p))

    results = []
    for case_id, mode_preds in by_case.items():
        scores: dict[str, float] = defaultdict(float)
        for mode_name, p in mode_preds:
            dx = p.get("primary_diagnosis")
            if dx:
                w = weights.get(mode_name, 1.0)
                scores[dx] += p.get("confidence", 0.5) * w

        if scores:
            best = max(scores, key=scores.get)
            # Collect all predictions for this case
            all_dx = set()
            for _, p in mode_preds:
                if p.get("primary_diagnosis"):
                    all_dx.add(p["primary_diagnosis"])
                for c in p.get("comorbid_diagnoses", []):
                    all_dx.add(c)
            comorbid = [d for d in all_dx if d != best]
        else:
            best = None
            comorbid = []

        results.append({
            "case_id": case_id,
            "primary_diagnosis": best,
            "comorbid_diagnoses": comorbid,
            "confidence": scores.get(best, 0.0) if best else 0.0,
            "decision": "diagnosis" if best else "abstain",
        })
    return results


def main():
    parser = argparse.ArgumentParser(description="Mode ensemble from existing predictions")
    parser.add_argument("--sweep-dir", required=True)
    parser.add_argument("--modes", required=True, help="Comma-separated condition names")
    parser.add_argument("--weights", default=None,
                        help="Comma-separated weights (same order as modes)")
    args = parser.parse_args()

    sweep_dir = Path(args.sweep_dir)
    mode_names = args.modes.split(",")
    if args.weights:
        weight_vals = [float(w) for w in args.weights.split(",")]
    else:
        weight_vals = [1.0] * len(mode_names)
    weights = dict(zip(mode_names, weight_vals))

    # Load predictions
    predictions_by_mode = {}
    for mode_name in mode_names:
        pred_path = sweep_dir / mode_name / "predictions.json"
        if not pred_path.exists():
            print(f"WARNING: {pred_path} not found", file=sys.stderr)
            continue
        with open(pred_path, encoding="utf-8") as f:
            data = json.load(f)
        predictions_by_mode[mode_name] = data["predictions"]
        print(f"Loaded {len(data['predictions'])} predictions from {mode_name}")

    # Load gold labels
    case_list = sweep_dir / "case_list.json"
    with open(case_list, encoding="utf-8") as f:
        gold_data = json.load(f)
    gold_map = {c["case_id"]: c["diagnoses"] for c in gold_data["cases"]}

    # Run ensemble
    ensemble = ensemble_predict(predictions_by_mode, weights)
    print(f"\nEnsemble: {len(ensemble)} cases")

    # Evaluate
    preds = []
    golds = []
    for r in ensemble:
        gold = gold_map.get(r["case_id"])
        if gold:
            pred_dx = [r["primary_diagnosis"]] if r["primary_diagnosis"] else ["unknown"]
            pred_dx += r.get("comorbid_diagnoses", [])
            preds.append(pred_dx)
            golds.append(gold)

    metrics = compute_diagnosis_metrics(preds, golds, normalize="parent")
    print(f"\nEnsemble metrics (parent-normalized):")
    for k, v in metrics.items():
        print(f"  {k}: {v:.3f}")

    # Compare with individual modes
    print(f"\nIndividual mode metrics:")
    for mode_name, mode_preds in predictions_by_mode.items():
        mp = []
        mg = []
        for p in mode_preds:
            gold = gold_map.get(p["case_id"])
            if gold:
                pd = [p["primary_diagnosis"]] if p["primary_diagnosis"] else ["unknown"]
                pd += p.get("comorbid_diagnoses", [])
                mp.append(pd)
                mg.append(gold)
        m = compute_diagnosis_metrics(mp, mg, normalize="parent")
        print(f"  {mode_name}: top1={m['top1_accuracy']:.3f} top3={m['top3_accuracy']:.3f}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test on MDD-5k 3-mode data**

```bash
uv run python scripts/ensemble_predict.py \
    --sweep-dir outputs/sweeps/n200_3mode_20260320_131920 \
    --modes hied_no_evidence,psycot_no_evidence,single_no_evidence \
    --weights 1.0,0.9,0.8
```

Expected: ensemble top1 > max(individual top1 values).

- [ ] **Step 3: Test on V10 LingxiDiag data**

```bash
uv run python scripts/ensemble_predict.py \
    --sweep-dir outputs/sweeps/v10_lingxidiag_20260320_222603 \
    --modes hied_no_evidence,psycot_no_evidence \
    --weights 1.0,0.9
```

- [ ] **Step 4: Commit**

```bash
git add scripts/ensemble_predict.py
git commit -m "feat: add confidence-weighted mode ensemble script"
```

---

## Chunk 2: Learned Ranker

### Task 4: Extract training features from existing predictions

**Context:** Build feature matrix from checker outputs in predictions.json. Each (case, disorder) pair becomes a training row. Label: 1 if this disorder matches gold, 0 otherwise.

**Files:**
- Create: `scripts/extract_ranker_features.py` (~120 lines)
- Output: `outputs/ranker_features/` (CSV files)

- [ ] **Step 1: Write feature extraction script**

```python
#!/usr/bin/env python3
"""Extract ranker training features from existing predictions.

For each case, each confirmed disorder becomes a row with features:
- threshold_ratio: criteria_met / criteria_required
- avg_confidence: mean confidence of met criteria
- core_score: weighted core criteria score (from calibrator)
- evidence_coverage: fraction of met criteria with evidence
- margin_score: excess criteria over threshold (normalized)
- n_criteria_total: total criteria count (disorder complexity)
- n_criteria_met: count of met criteria
- has_comorbid: binary, whether other disorders also confirmed
- confidence: calibrator confidence score
- is_correct: 1 if this disorder matches any gold label (target variable)

Usage:
    uv run python scripts/extract_ranker_features.py \
        --sweep-dir outputs/sweeps/v10_lingxidiag_20260320_222603 \
        --condition hied_no_evidence \
        --output outputs/ranker_features/lingxidiag_features.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from culturedx.eval.metrics import normalize_icd_code


def extract_features(predictions: list[dict], gold_map: dict[str, list[str]]) -> list[dict]:
    """Extract per-(case, disorder) feature rows from predictions."""
    rows = []
    for pred in predictions:
        case_id = pred["case_id"]
        gold = gold_map.get(case_id, [])
        gold_parent = {normalize_icd_code(g) for g in gold}

        primary = pred.get("primary_diagnosis")
        comorbid = pred.get("comorbid_diagnoses", [])
        all_dx = [primary] + comorbid if primary else comorbid

        criteria_results = pred.get("criteria_results", [])
        if not criteria_results:
            continue

        cr_map = {cr["disorder"]: cr for cr in criteria_results}

        for rank, dx in enumerate(all_dx):
            if not dx:
                continue
            cr = cr_map.get(dx, {})
            criteria = cr.get("criteria", [])
            met = [c for c in criteria if c.get("status") == "met"]

            avg_conf = sum(c.get("confidence", 0) for c in met) / len(met) if met else 0.0
            n_met = len(met)
            n_total = len(criteria)
            required = cr.get("criteria_required", 1)
            threshold_ratio = min(1.0, n_met / required) if required > 0 else 0.0
            margin = max(0, n_met - required) / max(n_total - required, 1) if n_total > required else 0.0
            has_evidence = sum(1 for c in met if c.get("evidence") and c["evidence"].strip()) / len(met) if met else 0.0

            dx_parent = normalize_icd_code(dx)
            is_correct = 1 if dx_parent in gold_parent else 0

            rows.append({
                "case_id": case_id,
                "disorder": dx,
                "rank": rank,
                "is_primary": 1 if rank == 0 else 0,
                "threshold_ratio": round(threshold_ratio, 4),
                "avg_confidence": round(avg_conf, 4),
                "n_criteria_met": n_met,
                "n_criteria_total": n_total,
                "criteria_required": required,
                "margin": round(margin, 4),
                "evidence_coverage": round(has_evidence, 4),
                "has_comorbid": 1 if len(all_dx) > 1 else 0,
                "confidence": round(pred.get("confidence", 0), 4),
                "is_correct": is_correct,
            })
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sweep-dir", required=True)
    parser.add_argument("--condition", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    sweep_dir = Path(args.sweep_dir)

    # Load gold
    with open(sweep_dir / "case_list.json", encoding="utf-8") as f:
        gold_data = json.load(f)
    gold_map = {c["case_id"]: c["diagnoses"] for c in gold_data["cases"]}

    # Load predictions
    pred_path = sweep_dir / args.condition / "predictions.json"
    with open(pred_path, encoding="utf-8") as f:
        preds = json.load(f)["predictions"]

    rows = extract_features(preds, gold_map)
    print(f"Extracted {len(rows)} feature rows from {len(preds)} cases")

    # Save
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved to {out}")

    # Stats
    correct = sum(r["is_correct"] for r in rows)
    primary_correct = sum(r["is_correct"] for r in rows if r["is_primary"])
    primary_total = sum(1 for r in rows if r["is_primary"])
    print(f"Correct labels: {correct}/{len(rows)} ({correct/len(rows):.1%})")
    print(f"Primary correct: {primary_correct}/{primary_total} ({primary_correct/primary_total:.1%})")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Extract features from both datasets**

```bash
mkdir -p outputs/ranker_features

uv run python scripts/extract_ranker_features.py \
    --sweep-dir outputs/sweeps/v10_lingxidiag_20260320_222603 \
    --condition hied_no_evidence \
    --output outputs/ranker_features/lingxidiag_hied.csv

uv run python scripts/extract_ranker_features.py \
    --sweep-dir outputs/sweeps/v10_mdd5k_20260320_233729 \
    --condition hied_no_evidence \
    --output outputs/ranker_features/mdd5k_hied.csv
```

- [ ] **Step 3: Commit**

```bash
git add scripts/extract_ranker_features.py outputs/ranker_features/
git commit -m "feat: add ranker feature extraction from predictions"
```

### Task 5: Train and evaluate learned ranker

**Files:**
- Create: `scripts/train_ranker.py` (~150 lines)
- Create: `src/culturedx/diagnosis/learned_ranker.py` (~60 lines)

- [ ] **Step 1: Write cross-dataset ranker training script**

```python
#!/usr/bin/env python3
"""Train learned ranker with cross-dataset validation.

Train on MDD-5k features, test on LingxiDiag (and vice versa).
This avoids train/test contamination while using all available data.

Usage:
    uv run python scripts/train_ranker.py \
        --train outputs/ranker_features/mdd5k_hied.csv \
        --test outputs/ranker_features/lingxidiag_hied.csv
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

FEATURE_COLS = [
    "threshold_ratio",
    "avg_confidence",
    "n_criteria_met",
    "n_criteria_total",
    "criteria_required",
    "margin",
    "evidence_coverage",
    "has_comorbid",
]


def load_features(path: str) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    """Load CSV → (X, y, raw_rows)."""
    rows = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    X = np.array([[float(row[c]) for c in FEATURE_COLS] for row in rows])
    y = np.array([int(row["is_correct"]) for row in rows])
    return X, y, rows


def evaluate_ranking(rows: list[dict], scores: np.ndarray) -> dict:
    """Evaluate ranking: for each case, does the highest-scored disorder match gold?"""
    # Group by case
    by_case: dict[str, list[tuple[float, dict]]] = defaultdict(list)
    for row, score in zip(rows, scores):
        by_case[row["case_id"]].append((score, row))

    correct = 0
    total = 0
    for case_id, entries in by_case.items():
        entries.sort(key=lambda x: -x[0])  # highest score first
        best = entries[0][1]
        total += 1
        if best["is_correct"] == "1" or best["is_correct"] == 1:
            correct += 1

    return {
        "top1_accuracy": correct / total if total > 0 else 0.0,
        "n_cases": total,
        "n_correct": correct,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", required=True)
    parser.add_argument("--test", required=True)
    parser.add_argument("--output", default=None, help="Output path for results JSON")
    args = parser.parse_args()

    # Load data
    X_train, y_train, rows_train = load_features(args.train)
    X_test, y_test, rows_test = load_features(args.test)

    print(f"Train: {len(X_train)} rows, {y_train.sum()} positive")
    print(f"Test:  {len(X_test)} rows, {y_test.sum()} positive")

    # Baseline: use existing calibrator confidence as ranking score
    conf_train = np.array([float(r["confidence"]) for r in rows_train])
    conf_test = np.array([float(r["confidence"]) for r in rows_test])

    baseline_train = evaluate_ranking(rows_train, conf_train)
    baseline_test = evaluate_ranking(rows_test, conf_test)
    print(f"\nBaseline (calibrator confidence):")
    print(f"  Train: top1={baseline_train['top1_accuracy']:.3f}")
    print(f"  Test:  top1={baseline_test['top1_accuracy']:.3f}")

    # Train logistic regression
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    model = LogisticRegression(C=1.0, max_iter=1000, random_state=42)
    model.fit(X_train_scaled, y_train)

    # Evaluate
    scores_train = model.predict_proba(X_train_scaled)[:, 1]
    scores_test = model.predict_proba(X_test_scaled)[:, 1]

    learned_train = evaluate_ranking(rows_train, scores_train)
    learned_test = evaluate_ranking(rows_test, scores_test)
    print(f"\nLearned ranker:")
    print(f"  Train: top1={learned_train['top1_accuracy']:.3f}")
    print(f"  Test:  top1={learned_test['top1_accuracy']:.3f}")

    delta = learned_test["top1_accuracy"] - baseline_test["top1_accuracy"]
    print(f"\n  Delta: {delta:+.3f} ({delta*100:+.1f}pp)")

    # Feature importance
    print(f"\nFeature coefficients:")
    for feat, coef in sorted(zip(FEATURE_COLS, model.coef_[0]), key=lambda x: -abs(x[1])):
        print(f"  {feat:25s}: {coef:+.4f}")

    # Save model info
    result = {
        "train_file": args.train,
        "test_file": args.test,
        "baseline_test_top1": baseline_test["top1_accuracy"],
        "learned_test_top1": learned_test["top1_accuracy"],
        "delta_pp": round(delta * 100, 1),
        "features": FEATURE_COLS,
        "coefficients": {f: round(c, 4) for f, c in zip(FEATURE_COLS, model.coef_[0])},
        "intercept": round(float(model.intercept_[0]), 4),
        "scaler_mean": scaler.mean_.tolist(),
        "scaler_scale": scaler.scale_.tolist(),
    }
    out = Path(args.output) if args.output else Path(args.train).parent / f"ranker_result_{Path(args.train).stem}_to_{Path(args.test).stem}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Train cross-dataset (MDD-5k → LingxiDiag)**

```bash
uv run python scripts/train_ranker.py \
    --train outputs/ranker_features/mdd5k_hied.csv \
    --test outputs/ranker_features/lingxidiag_hied.csv
```

- [ ] **Step 3: Train reverse direction (LingxiDiag → MDD-5k)**

```bash
uv run python scripts/train_ranker.py \
    --train outputs/ranker_features/lingxidiag_hied.csv \
    --test outputs/ranker_features/mdd5k_hied.csv
```

- [ ] **Step 4: Analyze results and decide on integration**

If delta ≥ +3pp on BOTH directions, proceed to integrate into `src/culturedx/diagnosis/learned_ranker.py`. If not, the fixed-weight calibrator stays.

- [ ] **Step 5: Commit**

```bash
git add scripts/train_ranker.py outputs/ranker_features/
git commit -m "feat: learned ranker training and cross-dataset evaluation"
```

---

## Chunk 3: Contrastive Analysis + Temporal Enhancement

### Task 6: Contrastive failure case-level analysis

**Files:**
- Create: `scripts/analyze_contrastive_diff.py` (~60 lines)

- [ ] **Step 1: Write contrastive diff analysis**

```python
#!/usr/bin/env python3
"""Case-level diff: contrastive ON vs OFF."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from culturedx.eval.metrics import normalize_icd_code


def main() -> None:
    parser = argparse.ArgumentParser(description="Contrastive ON vs OFF case-level diff")
    parser.add_argument("off_dir", help="Contrastive OFF predictions dir")
    parser.add_argument("on_dir", help="Contrastive ON predictions dir")
    parser.add_argument("case_list", help="Path to case_list.json")
    args = parser.parse_args()

    with open(Path(args.off_dir) / "predictions.json", encoding="utf-8") as f:
        off_preds: dict[str, dict] = {p["case_id"]: p for p in json.load(f)["predictions"]}
    with open(Path(args.on_dir) / "predictions.json", encoding="utf-8") as f:
        on_preds: dict[str, dict] = {p["case_id"]: p for p in json.load(f)["predictions"]}
    with open(args.case_list, encoding="utf-8") as f:
        gold_map: dict[str, list[str]] = {c["case_id"]: c["diagnoses"] for c in json.load(f)["cases"]}

    helped: list[dict] = []  # wrong→correct
    hurt: list[dict] = []    # correct→wrong
    for cid in off_preds:
        gold = {normalize_icd_code(g) for g in gold_map.get(cid, [])}
        off_dx = normalize_icd_code(off_preds[cid]["primary_diagnosis"] or "")
        on_dx = normalize_icd_code(on_preds[cid]["primary_diagnosis"] or "")
        off_ok = off_dx in gold
        on_ok = on_dx in gold
        if off_ok and not on_ok:
            hurt.append({"case_id": cid, "gold": list(gold), "off": off_dx, "on": on_dx,
                         "off_conf": off_preds[cid]["confidence"], "on_conf": on_preds[cid]["confidence"]})
        elif not off_ok and on_ok:
            helped.append({"case_id": cid, "gold": list(gold), "off": off_dx, "on": on_dx,
                           "off_conf": off_preds[cid]["confidence"], "on_conf": on_preds[cid]["confidence"]})

    print(f"Contrastive HELPED: {len(helped)} cases (wrong→correct)")
    for h in helped[:10]:
        print(f"  {h['case_id']}: {h['off']}→{h['on']} gold={h['gold']}")
    print(f"\nContrastive HURT: {len(hurt)} cases (correct→wrong)")
    for h in hurt[:10]:
        print(f"  {h['case_id']}: {h['off']}→{h['on']} gold={h['gold']} off_conf={h['off_conf']:.3f} on_conf={h['on_conf']:.3f}")
    print(f"\nNet: {len(helped) - len(hurt):+d} cases")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run on LingxiDiag (where contrastive hurt)**

```bash
uv run python scripts/analyze_contrastive_diff.py \
    outputs/sweeps/contrastive_off_lingxidiag_20260321_105016/hied_no_evidence \
    outputs/sweeps/contrastive_on_lingxidiag_20260321_115845/hied_no_evidence \
    outputs/sweeps/contrastive_off_lingxidiag_20260321_105016/case_list.json
```

- [ ] **Step 3: Run on MDD-5k (where contrastive helped)**

```bash
uv run python scripts/analyze_contrastive_diff.py \
    outputs/sweeps/contrastive_off_mdd5k_20260321_131315/hied_no_evidence \
    outputs/sweeps/contrastive_on_mdd5k_20260321_165032/hied_no_evidence \
    outputs/sweeps/contrastive_off_mdd5k_20260321_131315/case_list.json
```

- [ ] **Step 4: Commit**

```bash
git add scripts/analyze_contrastive_diff.py
git commit -m "feat: contrastive case-level diff analysis script"
```

### Task 7: Enhance F41.1 temporal criterion A prompt

**Files:**
- Modify: `prompts/agents/criterion_checker.jinja2` (or `.md`)
- Test: Run 20-case pilot with modified prompt

- [ ] **Step 1: Find and read the criterion checker prompt**

```bash
find prompts/ -name "*criterion*" -o -name "*checker*" | head -10
```

- [ ] **Step 2: Add temporal inference heuristic for F41.1 criterion A**

Add to the prompt template (Chinese section), conditional on criterion_id == "A" and disorder_code == "F41.1":

```
## 时间推断提示（仅用于 F41.1 标准 A：焦虑持续 ≥6 个月）
中文患者很少明确说出焦虑持续时间。请从以下间接证据推断：
- 反复就诊记录（"看了好几次医生""吃了很久的药"）→ 暗示持续数月
- 工作/学业受影响的时间跨度（"这学期成绩都下降了""好几个月没上班"）→ ≥4个月
- 季节性参照（"从去年冬天开始""过年前就这样了"）→ 可推算具体时长
- 慢性化表述（"一直""总是""老是"）→ 暗示长期状态
如果有任何间接证据支持 ≥6 个月，标记为 met 并注明推断依据。
```

- [ ] **Step 3: Run 20-case pilot to validate**

```bash
uv run python scripts/ablation_sweep.py \
    --provider vllm --model Qwen/Qwen3-32B-AWQ \
    --modes hied -n 20 --seed 42 --dataset lingxidiag16k \
    --sweep-name temporal_pilot
```

Compare F41.1 criterion A MET rate with V10 baseline (31%).

- [ ] **Step 4: If improved, run full N=200**

- [ ] **Step 5: Commit**

```bash
git add prompts/
git commit -m "feat: add temporal inference heuristic for F41.1 criterion A"
```

---

## Chunk 4: Cross-lingual Validation

### Task 8: Run cross-lingual evidence gap experiment

**Context:** E-DAIC adapter currently sets `diagnoses=[]` and `coding_system="dsm5"`. The sweep evaluator skips cases with empty diagnoses. Before running, we must verify the adapter outputs usable gold labels. If E-DAIC has binary depression labels (PHQ-8 ≥ 10), use binary F1 evaluation instead of multi-class ICD-10 metrics.

**Files:**
- Possibly modify: `src/culturedx/data/adapters/edaic.py` (if gold labels need mapping)
- Run: `scripts/ablation_sweep.py`
- Analyze: `src/culturedx/eval/cross_lingual.py`

- [ ] **Step 1: Inspect E-DAIC adapter and data format**

```bash
uv run python -c "
from culturedx.data.adapters import get_adapter
adapter = get_adapter('edaic', 'data/raw/edaic')
cases = adapter.load()
print(f'E-DAIC: {len(cases)} cases')
if cases:
    c = cases[0]
    print(f'  lang={c.language}, diagnoses={c.diagnoses}, coding_system={c.coding_system}')
    print(f'  severity={c.severity}')
    # Check how many have non-empty diagnoses
    with_dx = sum(1 for c in cases if c.diagnoses)
    print(f'  Cases with diagnoses: {with_dx}/{len(cases)}')
"
```

- [ ] **Step 2: Assess adapter viability**

If `diagnoses=[]` for all cases, the cross-lingual experiment requires adapter modification:
- Map PHQ-8 ≥ 10 → `diagnoses=["F32"]` (binary depression)
- Map PHQ-8 < 10 → `diagnoses=["healthy"]`
- This enables binary comparison: does evidence help detect F32 in EN vs CN?

If adapter modification is needed, update `src/culturedx/data/adapters/edaic.py` and commit.

- [ ] **Step 3: Run English baseline (no evidence)**

```bash
uv run python scripts/ablation_sweep.py \
    --provider vllm --model Qwen/Qwen3-32B-AWQ \
    --modes hied,single -n 200 --seed 42 --dataset edaic \
    --sweep-name edaic_baseline
```

- [ ] **Step 4: Run English with evidence**

```bash
uv run python scripts/ablation_sweep.py \
    --provider vllm --model Qwen/Qwen3-32B-AWQ \
    --modes hied --evidence-ablation --retriever bge-m3 \
    -n 200 --seed 42 --dataset edaic \
    --sweep-name edaic_evidence
```

- [ ] **Step 5: Compute cross-lingual evidence delta**

```bash
uv run python -c "
import json
from pathlib import Path

# Load CN evidence delta (from Task 1-2 results)
cn_dirs = sorted(Path('outputs/sweeps').glob('evidence_lingxidiag_*'))
cn_no_ev = cn_dirs[0] / 'hied_no_evidence/metrics.json' if cn_dirs else None
cn_with_ev = cn_dirs[0] / 'hied_bge-m3_evidence/metrics.json' if cn_dirs else None

# Load EN evidence delta
en_dirs = sorted(Path('outputs/sweeps').glob('edaic_baseline_*'))
en_ev_dirs = sorted(Path('outputs/sweeps').glob('edaic_evidence_*'))
en_no_ev = en_dirs[0] / 'hied_no_evidence/metrics.json' if en_dirs else None
en_with_ev = en_ev_dirs[0] / 'hied_bge-m3_evidence/metrics.json' if en_ev_dirs else None

for label, no_ev_path, with_ev_path in [('CN', cn_no_ev, cn_with_ev), ('EN', en_no_ev, en_with_ev)]:
    if no_ev_path and no_ev_path.exists() and with_ev_path and with_ev_path.exists():
        no_ev = json.load(open(no_ev_path, encoding='utf-8'))
        with_ev = json.load(open(with_ev_path, encoding='utf-8'))
        no_top1 = no_ev.get('metrics_parent_normalized', {}).get('top1_accuracy', 0)
        with_top1 = with_ev.get('metrics_parent_normalized', {}).get('top1_accuracy', 0)
        delta = with_top1 - no_top1
        print(f'{label}: no_evidence={no_top1:.3f}  with_evidence={with_top1:.3f}  delta={delta:+.3f} ({delta*100:+.1f}pp)')
    else:
        print(f'{label}: missing metrics files')

print()
print('Core thesis test: CN evidence delta should be LARGER than EN evidence delta')
print('(because Chinese somatization requires explicit culture-aware mapping)')
"
```

- [ ] **Step 6: Commit results**

```bash
git add outputs/sweeps/edaic_*
git commit -m "data: cross-lingual evidence gap experiment (E-DAIC)"
```
