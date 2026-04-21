"""Smoke tests for the stacker feature builder."""
from __future__ import annotations

import json
import pickle
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from stacker.build_features import (  # noqa: E402
    FEATURE_NAMES,
    N_FEATURES,
    build_features,
    feature_names,
)


def test_feature_names_deterministic():
    # feature_names() should return the same list every call, same order.
    first = feature_names()
    second = feature_names()
    assert first == second
    assert len(first) == 31  # 12 + 5 + 12 + 1 + 1
    # Sanity: first block should be TF-IDF probs for paper-12 classes
    from culturedx.eval.lingxidiag_paper import PAPER_12_CLASSES
    for i, c in enumerate(PAPER_12_CLASSES):
        assert first[i] == f"tfidf_p__{c}"


def test_build_features_minimum_shape():
    tfidf_rec = {
        "case_id": "a1",
        "primary_diagnosis": "F32",
        "ranked_codes": ["F32", "F41", "F39", "F31", "F42", "F43", "F45",
                         "F51", "F98", "F20", "Z71", "Others"],
        "proba_scores": [0.70, 0.12, 0.06, 0.04, 0.03, 0.02, 0.01,
                         0.01, 0.005, 0.003, 0.001, 0.001],
    }
    dtv_rec = {
        "case_id": "a1",
        "primary_diagnosis": "F41.1",
        "decision_trace": {
            "raw_checker_outputs": [
                {"disorder_code": "F32", "met_ratio": 1.1},
                {"disorder_code": "F41.1", "met_ratio": 0.9},
            ],
            "diagnostician_ranked": [
                {"code": "F41.1", "confidence": 0.72},
                {"code": "F32", "confidence": 0.55},
            ],
        },
    }
    feats = build_features(tfidf_rec, dtv_rec)
    assert len(feats) == N_FEATURES
    # TF-IDF margin = 0.70 - 0.12 = 0.58
    margin = feats[FEATURE_NAMES.index("tfidf_top1_margin")]
    assert abs(margin - 0.58) < 1e-9
    # abstain=0 (DtV had output)
    abstain = feats[FEATURE_NAMES.index("dtv_abstain_flag")]
    assert abstain == 0.0


def test_abstain_flag_on_empty_dtv():
    tfidf_rec = {
        "case_id": "a2",
        "primary_diagnosis": "F32",
        "ranked_codes": ["F32"] + ["F41"] * 11,
        "proba_scores": [0.5] + [0.04] * 11,
    }
    dtv_rec = {"case_id": "a2"}  # no primary, no trace
    feats = build_features(tfidf_rec, dtv_rec)
    abstain = feats[FEATURE_NAMES.index("dtv_abstain_flag")]
    assert abstain == 1.0


def test_build_features_cli_roundtrip(tmp_path):
    tfidf_path = tmp_path / "tfidf.jsonl"
    dtv_path = tmp_path / "dtv.jsonl"
    out_path = tmp_path / "features.jsonl"

    # Build minimal aligned predictions
    cases = []
    for cid in ["c1", "c2", "c3"]:
        tfidf_pred = {
            "case_id": cid,
            "gold_diagnoses": ["F32"],
            "primary_diagnosis": "F32",
            "ranked_codes": ["F32"] + [c for c in [
                "F20", "F31", "F39", "F41", "F42", "F43", "F45",
                "F51", "F98", "Z71", "Others",
            ]],
            "proba_scores": [0.6] + [0.04] * 11,
        }
        dtv_pred = {
            "case_id": cid,
            "primary_diagnosis": "F32",
            "decision_trace": {
                "raw_checker_outputs": [{"disorder_code": "F32", "met_ratio": 1.0}],
                "diagnostician_ranked": [{"code": "F32", "confidence": 0.8}],
            },
        }
        cases.append((tfidf_pred, dtv_pred))

    with tfidf_path.open("w", encoding="utf-8") as f:
        for t, _ in cases:
            f.write(json.dumps(t) + "\n")
    with dtv_path.open("w", encoding="utf-8") as f:
        for _, d in cases:
            f.write(json.dumps(d) + "\n")

    script = ROOT / "scripts" / "stacker" / "build_features.py"
    env = {"PYTHONPATH": str(ROOT / "src")}
    import os
    env.update({k: v for k, v in os.environ.items() if k not in env})
    result = subprocess.run(
        [sys.executable, str(script),
         "--tfidf-pred", str(tfidf_path),
         "--dtv-pred", str(dtv_path),
         "--eval-split", "dev_hpo",
         "--out", str(out_path)],
        capture_output=True, text=True, env=env,
    )
    if result.returncode != 0:
        print("STDERR:", result.stderr, file=sys.stderr)
    assert result.returncode == 0, result.stderr

    lines = out_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    for line in lines:
        rec = json.loads(line)
        assert len(rec["features"]) == N_FEATURES
        assert rec["eval_split"] == "dev_hpo"
        assert rec["gold_parents"] == ["F32"]


def test_train_stacker_refuses_test_final_features(tmp_path):
    """Training must refuse features labeled eval_split=test_final."""
    features_path = tmp_path / "features.jsonl"
    bad_rec = {
        "case_id": "c1",
        "eval_split": "test_final",
        "features": [0.0] * N_FEATURES,
        "feature_names": FEATURE_NAMES,
        "gold_parents": ["F32"],
    }
    features_path.write_text(json.dumps(bad_rec) + "\n", encoding="utf-8")

    script = ROOT / "scripts" / "stacker" / "train_stacker.py"
    out_dir = tmp_path / "stacker_out"
    env = {"PYTHONPATH": str(ROOT / "src")}
    import os
    env.update({k: v for k, v in os.environ.items() if k not in env})
    result = subprocess.run(
        [sys.executable, str(script),
         "--features", str(features_path),
         "--out-dir", str(out_dir)],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode != 0, "trainer did not refuse test_final features"
    assert "SAFETY STOP" in (result.stderr + result.stdout)


def test_eval_stacker_accepts_label_encoder_order_and_writes_metrics(tmp_path):
    from sklearn.dummy import DummyClassifier
    from sklearn.preprocessing import LabelEncoder

    from culturedx.eval.lingxidiag_paper import PAPER_12_CLASSES

    features_path = tmp_path / "features.jsonl"
    model_path = tmp_path / "stacker_lr.pkl"
    tfidf_path = tmp_path / "tfidf.jsonl"
    dtv_path = tmp_path / "dtv.jsonl"
    out_dir = tmp_path / "eval_out"

    feature_names = ["f0"]
    feature_rows = [
        {
            "case_id": "c1",
            "eval_split": "test_final",
            "features": [0.0],
            "feature_names": feature_names,
            "gold_parents": ["F32"],
        },
        {
            "case_id": "c2",
            "eval_split": "test_final",
            "features": [1.0],
            "feature_names": feature_names,
            "gold_parents": ["F41"],
        },
    ]
    with features_path.open("w", encoding="utf-8") as f:
        for rec in feature_rows:
            f.write(json.dumps(rec) + "\n")

    le = LabelEncoder()
    le.fit(PAPER_12_CLASSES)
    y_train = le.transform(PAPER_12_CLASSES)
    model = DummyClassifier(strategy="uniform", random_state=0)
    model.fit([[float(i)] for i in range(len(PAPER_12_CLASSES))], y_train)
    with model_path.open("wb") as f:
        pickle.dump({"model": model, "label_encoder": le}, f)

    baseline_rows = [
        {"case_id": "c1", "primary_diagnosis": "F32"},
        {"case_id": "c2", "primary_diagnosis": "F41"},
    ]
    for path in [tfidf_path, dtv_path]:
        with path.open("w", encoding="utf-8") as f:
            for rec in baseline_rows:
                f.write(json.dumps(rec) + "\n")

    script = ROOT / "scripts" / "stacker" / "eval_stacker.py"
    env = {"PYTHONPATH": str(ROOT / "src")}
    import os
    env.update({k: v for k, v in os.environ.items() if k not in env})
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--features", str(features_path),
            "--model", str(model_path),
            "--tfidf-pred", str(tfidf_path),
            "--dtv-pred", str(dtv_path),
            "--out-dir", str(out_dir),
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        print("STDOUT:", result.stdout, file=sys.stderr)
        print("STDERR:", result.stderr, file=sys.stderr)
    assert result.returncode == 0, result.stderr

    metrics = json.loads((out_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["split"] == "test_final"
    assert metrics["n"] == 2
    assert metrics["table4"]["12class_n"] == 2
