"""Evaluate temporal extraction NLP tools for Chinese clinical text.

Benchmarks: jionlp, dateparser, ChineseTimeNLP, stanza, regex (current)
on real clinical dialogue from LingxiDiag-16K and MDD-5k.
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


# ---------------------------------------------------------------------------
# Test cases: real Chinese clinical patient turns with temporal expressions
# Ground truth: manually annotated durations
# ---------------------------------------------------------------------------

@dataclass
class TemporalTestCase:
    """A test case for temporal extraction."""
    id: str
    text: str
    expected_durations: list[str]  # human-readable duration strings found
    expected_months: float | None  # ground-truth duration in months (None = ambiguous)
    expected_meets_6mo: bool | None  # should meet 6-month criterion?
    category: str  # "explicit", "relative", "implicit", "short", "none"
    source: str  # dataset name


TEST_CASES = [
    # --- Explicit durations ---
    TemporalTestCase(
        id="E1", category="explicit", source="lingxidiag",
        text="我失眠大概有三个月了，每天晚上翻来覆去睡不着",
        expected_durations=["三个月"],
        expected_months=3.0, expected_meets_6mo=False,
    ),
    TemporalTestCase(
        id="E2", category="explicit", source="lingxidiag",
        text="这种情况已经持续了七年了，从高中就开始了",
        expected_durations=["七年", "从高中就开始"],
        expected_months=84.0, expected_meets_6mo=True,
    ),
    TemporalTestCase(
        id="E3", category="explicit", source="mdd5k",
        text="我焦虑紧张大概半年多了，总是担心各种事情",
        expected_durations=["半年多"],
        expected_months=7.0, expected_meets_6mo=True,
    ),
    TemporalTestCase(
        id="E4", category="explicit", source="lingxidiag",
        text="心情低落两个月了，什么都不想做",
        expected_durations=["两个月"],
        expected_months=2.0, expected_meets_6mo=False,
    ),
    TemporalTestCase(
        id="E5", category="explicit", source="mdd5k",
        text="已经吃了两年的药了，但是效果不太好，症状反反复复",
        expected_durations=["两年"],
        expected_months=24.0, expected_meets_6mo=True,
    ),
    TemporalTestCase(
        id="E6", category="explicit", source="lingxidiag",
        text="持续了五个月左右，情绪一直很低落",
        expected_durations=["五个月"],
        expected_months=5.0, expected_meets_6mo=False,
    ),
    TemporalTestCase(
        id="E7", category="explicit", source="mdd5k",
        text="断断续续有十年了，中间好过一阵子又复发了",
        expected_durations=["十年"],
        expected_months=120.0, expected_meets_6mo=True,
    ),

    # --- Relative time references ---
    TemporalTestCase(
        id="R1", category="relative", source="lingxidiag",
        text="去年冬天开始的，那时候刚失业",
        expected_durations=["去年冬天"],
        expected_months=15.0, expected_meets_6mo=True,
    ),
    TemporalTestCase(
        id="R2", category="relative", source="mdd5k",
        text="从去年九月份就开始焦虑了，一直到现在",
        expected_durations=["去年九月份"],
        expected_months=18.0, expected_meets_6mo=True,
    ),
    TemporalTestCase(
        id="R3", category="relative", source="lingxidiag",
        text="前年离婚以后就开始这样了，整个人都垮了",
        expected_durations=["前年"],
        expected_months=24.0, expected_meets_6mo=True,
    ),
    TemporalTestCase(
        id="R4", category="relative", source="mdd5k",
        text="上个月刚做了手术，术后一直睡不好",
        expected_durations=["上个月"],
        expected_months=1.0, expected_meets_6mo=False,
    ),

    # --- Implicit/indirect duration cues ---
    TemporalTestCase(
        id="I1", category="implicit", source="lingxidiag",
        text="从上高中就开始了，现在大三了，一直都这样",
        expected_durations=["从上高中到大三"],
        expected_months=60.0, expected_meets_6mo=True,
    ),
    TemporalTestCase(
        id="I2", category="implicit", source="mdd5k",
        text="反复发作很多次了，看了好几个医院都看不好",
        expected_durations=["反复多次"],
        expected_months=None, expected_meets_6mo=True,
    ),
    TemporalTestCase(
        id="I3", category="implicit", source="lingxidiag",
        text="退休以后就一直这样，越来越严重了",
        expected_durations=["退休以后"],
        expected_months=None, expected_meets_6mo=True,
    ),
    TemporalTestCase(
        id="I4", category="implicit", source="mdd5k",
        text="很久了，具体多久记不清了，反正好几年了",
        expected_durations=["好几年"],
        expected_months=36.0, expected_meets_6mo=True,
    ),

    # --- Short duration / recent onset ---
    TemporalTestCase(
        id="S1", category="short", source="lingxidiag",
        text="最近才开始的，就这几天心慌特别厉害",
        expected_durations=["最近", "这几天"],
        expected_months=0.1, expected_meets_6mo=False,
    ),
    TemporalTestCase(
        id="S2", category="short", source="mdd5k",
        text="上周开始失眠，这个星期更严重了",
        expected_durations=["上周", "这个星期"],
        expected_months=0.5, expected_meets_6mo=False,
    ),
    TemporalTestCase(
        id="S3", category="short", source="lingxidiag",
        text="刚刚开始有这个问题，也就三四天吧",
        expected_durations=["三四天"],
        expected_months=0.1, expected_meets_6mo=False,
    ),

    # --- No clear temporal info ---
    TemporalTestCase(
        id="N1", category="none", source="lingxidiag",
        text="我就是心情不好，什么都不想做，吃不下饭",
        expected_durations=[],
        expected_months=None, expected_meets_6mo=None,
    ),
    TemporalTestCase(
        id="N2", category="none", source="mdd5k",
        text="头疼，胸闷，浑身没劲",
        expected_durations=[],
        expected_months=None, expected_meets_6mo=None,
    ),
]


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------

@dataclass
class ToolResult:
    """Result from a single tool on a single test case."""
    tool_name: str
    case_id: str
    extracted_entities: list[str]
    estimated_months: float | None
    raw_output: str
    error: str | None = None
    latency_ms: float = 0.0


def eval_jionlp(text: str) -> tuple[list[str], float | None, str]:
    """Evaluate jionlp parse_time."""
    import jionlp as jio
    results = []
    raw_parts = []
    try:
        parsed = jio.parse_time(text, time_base=None)
        if parsed:
            raw_parts.append(str(parsed))
            if isinstance(parsed, dict):
                results.append(str(parsed.get("time", [parsed])))
            elif isinstance(parsed, list):
                for p in parsed:
                    results.append(str(p))
            else:
                results.append(str(parsed))
    except Exception as e:
        raw_parts.append(f"parse_time error: {e}")

    # Also try time_extractor
    try:
        extracted = jio.TimeExtractor()
        te_result = extracted(text)
        if te_result:
            raw_parts.append(f"TimeExtractor: {te_result}")
            for item in te_result:
                if isinstance(item, dict):
                    results.append(item.get("time_candidate", str(item)))
                else:
                    results.append(str(item))
    except Exception as e:
        raw_parts.append(f"TimeExtractor error: {e}")

    return results, None, "\n".join(raw_parts)


def eval_dateparser(text: str) -> tuple[list[str], float | None, str]:
    """Evaluate dateparser search_dates."""
    import dateparser.search as ds
    results = []
    raw = ""
    try:
        found = ds.search_dates(text, languages=["zh"])
        raw = str(found)
        if found:
            for text_match, dt in found:
                results.append(f"{text_match} -> {dt}")
    except Exception as e:
        raw = f"Error: {e}"
    return results, None, raw


def eval_chinese_time_nlp(text: str) -> tuple[list[str], float | None, str]:
    """Evaluate ChineseTimeNLP."""
    from ChineseTimeNLP import TimeNormalizer
    tn = TimeNormalizer()
    results = []
    raw = ""
    try:
        parsed = tn.parse(target=text)
        raw = str(parsed)
        if parsed:
            results.append(str(parsed))
    except Exception as e:
        raw = f"Error: {e}"
    return results, None, raw


def eval_stanza(text: str, nlp) -> tuple[list[str], float | None, str]:
    """Evaluate stanza NER for temporal entities."""
    results = []
    raw_parts = []
    try:
        doc = nlp(text)
        for sent in doc.sentences:
            for ent in sent.entities:
                if ent.type in ("DATE", "TIME", "DURATION", "SET"):
                    results.append(f"[{ent.type}] {ent.text}")
                    raw_parts.append(f"{ent.type}: {ent.text}")
            # Also check tokens for temporal POS tags
            for token in sent.tokens:
                for word in token.words:
                    if word.upos == "NUM" or (word.xpos and "t" in word.xpos.lower()):
                        pass  # captured by NER above
    except Exception as e:
        raw_parts.append(f"Error: {e}")
    return results, None, "; ".join(raw_parts) if raw_parts else "no entities"


def eval_current_regex(text: str) -> tuple[list[str], float | None, str]:
    """Evaluate current CultureDx temporal.py regex."""
    from culturedx.evidence.temporal import _extract_from_text, _check_short_duration, _infer_duration
    
    matches = _extract_from_text(text, turn_id=0)
    has_short = _check_short_duration(text)
    features = _infer_duration(matches, has_short)
    
    results = [f"[{m.category}] {m.text}" for m in matches]
    est = features.estimated_months
    raw = (
        f"matches={len(matches)}, confidence={features.duration_confidence}, "
        f"months={est}, meets_6mo={features.meets_6month_criterion}\n"
        f"reasoning: {features.reasoning}"
    )
    return results, est, raw


# ---------------------------------------------------------------------------
# Main evaluation
# ---------------------------------------------------------------------------

def run_evaluation():
    print("=" * 80)
    print("TEMPORAL EXTRACTION TOOL EVALUATION")
    print("=" * 80)
    print(f"Test cases: {len(TEST_CASES)}")
    print()

    # Initialize tools
    tools: dict[str, callable] = {}
    
    # 1. Current regex (always available)
    tools["regex_current"] = lambda text: eval_current_regex(text)
    
    # 2. jionlp
    try:
        import jionlp
        tools["jionlp"] = lambda text: eval_jionlp(text)
        print("[OK] jionlp loaded")
    except ImportError:
        print("[SKIP] jionlp not installed")
    
    # 3. dateparser
    try:
        import dateparser
        tools["dateparser"] = lambda text: eval_dateparser(text)
        print("[OK] dateparser loaded")
    except ImportError:
        print("[SKIP] dateparser not installed")
    
    # 4. ChineseTimeNLP
    try:
        from ChineseTimeNLP import TimeNormalizer
        tools["ChineseTimeNLP"] = lambda text: eval_chinese_time_nlp(text)
        print("[OK] ChineseTimeNLP loaded")
    except ImportError:
        print("[SKIP] ChineseTimeNLP not installed")
    
    # 5. stanza
    try:
        import stanza
        print("[...] Loading stanza Chinese model...")
        try:
            stanza_nlp = stanza.Pipeline(
                "zh", processors="tokenize,ner",
                download_method=stanza.DownloadMethod.REUSE_RESOURCES,
                logging_level="ERROR",
            )
        except Exception:
            stanza.download("zh", logging_level="ERROR")
            stanza_nlp = stanza.Pipeline(
                "zh", processors="tokenize,ner",
                logging_level="ERROR",
            )
        tools["stanza"] = lambda text, nlp=stanza_nlp: eval_stanza(text, nlp)
        print("[OK] stanza loaded")
    except ImportError:
        print("[SKIP] stanza not installed")
    except Exception as e:
        print(f"[SKIP] stanza failed to load: {e}")
    
    print(f"\nTools to evaluate: {list(tools.keys())}")
    print()
    
    # Run evaluation
    all_results: dict[str, list[ToolResult]] = {name: [] for name in tools}
    
    for case in TEST_CASES:
        print(f"--- Case {case.id} [{case.category}] ---")
        print(f"  Text: {case.text[:60]}...")
        print(f"  Expected: {case.expected_durations} -> {case.expected_months}mo, 6mo={case.expected_meets_6mo}")
        
        for tool_name, tool_fn in tools.items():
            t0 = time.perf_counter()
            try:
                entities, est_months, raw = tool_fn(case.text)
                error = None
            except Exception as e:
                entities, est_months, raw = [], None, ""
                error = f"{type(e).__name__}: {e}"
            latency = (time.perf_counter() - t0) * 1000
            
            result = ToolResult(
                tool_name=tool_name,
                case_id=case.id,
                extracted_entities=entities,
                estimated_months=est_months,
                raw_output=raw[:200],
                error=error,
                latency_ms=latency,
            )
            all_results[tool_name].append(result)
            
            status = "ERR" if error else ("OK" if entities else "MISS")
            print(f"  [{tool_name:16s}] {status:4s} | {len(entities):2d} entities | {latency:6.1f}ms | {entities[:3]}")
        print()
    
    # Aggregate metrics
    print("\n" + "=" * 80)
    print("AGGREGATE METRICS")
    print("=" * 80)
    
    for tool_name, results in all_results.items():
        total = len(results)
        detected = sum(1 for r in results if r.extracted_entities)
        errors = sum(1 for r in results if r.error)
        avg_latency = sum(r.latency_ms for r in results) / total if total else 0
        
        # Detection rate by category
        cat_stats: dict[str, tuple[int, int]] = {}
        for case, result in zip(TEST_CASES, results):
            cat = case.category
            if cat not in cat_stats:
                cat_stats[cat] = [0, 0]
            cat_stats[cat][1] += 1
            if result.extracted_entities:
                cat_stats[cat][0] += 1
        
        # 6-month criterion accuracy (for regex_current only since others don't compute it)
        if tool_name == "regex_current":
            correct_6mo = 0
            total_6mo = 0
            for case, result in zip(TEST_CASES, results):
                if case.expected_meets_6mo is not None:
                    total_6mo += 1
                    # Parse meets_6mo from raw output
                    meets = "meets_6mo=True" in result.raw_output
                    if meets == case.expected_meets_6mo:
                        correct_6mo += 1
            print(f"\n{'='*40}")
            print(f"Tool: {tool_name}")
            print(f"  Detection rate: {detected}/{total} ({detected/total*100:.0f}%)")
            print(f"  Errors: {errors}/{total}")
            print(f"  Avg latency: {avg_latency:.1f}ms")
            print(f"  6-month criterion accuracy: {correct_6mo}/{total_6mo} ({correct_6mo/total_6mo*100:.0f}%)" if total_6mo else "")
            for cat, (hit, cnt) in sorted(cat_stats.items()):
                print(f"    {cat:12s}: {hit}/{cnt} ({hit/cnt*100:.0f}%)")
        else:
            print(f"\n{'='*40}")
            print(f"Tool: {tool_name}")
            print(f"  Detection rate: {detected}/{total} ({detected/total*100:.0f}%)")
            print(f"  Errors: {errors}/{total}")
            print(f"  Avg latency: {avg_latency:.1f}ms")
            for cat, (hit, cnt) in sorted(cat_stats.items()):
                print(f"    {cat:12s}: {hit}/{cnt} ({hit/cnt*100:.0f}%)")
    
    # Save raw results
    out_path = Path("outputs/temporal_eval_results.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    serializable = {}
    for tool_name, results in all_results.items():
        serializable[tool_name] = [asdict(r) for r in results]
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)
    print(f"\nRaw results saved to {out_path}")


if __name__ == "__main__":
    run_evaluation()
