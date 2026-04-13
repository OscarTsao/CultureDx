"""Scope-aware negation detection for Chinese clinical text.

Uses clause-local scope resolution plus optional dependency parsing to
determine whether a symptom mention is actually negated.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

# stanza is imported on-demand when mode="stanza-dep" is requested


NEGATION_CUES = (
    "沒有",
    "没有",
    "否認",
    "否认",
    "不是",
    "不會",
    "不会",
    "不能",
    "不太",
    "沒",
    "没",
    "不",
    "無",
    "无",
    "未",
)

SCOPE_DELIMITERS = (
    "但是",
    "不過",
    "不过",
    "可是",
    "然而",
    "就是",
    "只是",
    "；",
    "。",
    "，",
    "但",
)

EXCEPTION_PATTERNS = (
    r"不是我",
    r"不是說",
    r"不是说",
    r"不是因為",
    r"不是因为",
    r"不知道",
    r"不好意思",
    r"不一定",
)

POSITIVE_NEGATION_TERMS = (
    "睡不著覺",
    "睡不著",
    "睡不着觉",
    "睡不着",
    "睡不好",
    "吃不下飯",
    "吃不下饭",
    "吃不下",
    "坐不住",
    "控制不住",
    "集中不了",
    "放松不了",
    "放鬆不了",
    "忍不住",
    "受不了",
    "停不下來",
    "停不下来",
    "想不開",
    "想不开",
    "高興不起來",
    "高兴不起来",
    "打不起精神",
    "提不起勁",
    "提不起劲",
    "透不過氣",
    "透不过气",
    "喘不過氣",
    "喘不过气",
    "不想做事",
    "沒興趣",
    "沒有興趣",
    "没兴趣",
)

_CUE_RE = re.compile("|".join(re.escape(cue) for cue in sorted(NEGATION_CUES, key=len, reverse=True)))
_DELIMITER_RE = re.compile(
    "|".join(re.escape(delim) for delim in sorted(SCOPE_DELIMITERS, key=len, reverse=True))
)
_EXCEPTION_RE = tuple(re.compile(pattern) for pattern in EXCEPTION_PATTERNS)
_NOMINAL_SCOPE_BREAK_RE = re.compile(r"(出现|出現|发生|發生|导致|導致|引起|造成|伴随|伴隨|并|並|而)")
_DOUBLE_NEGATION_PREFIX_RE = re.compile(r"(并非|並非|并不是|並不是|并不|並不|不是|非).{0,4}$")
_DOUBLE_NEGATION_ANCESTORS = frozenset({"并非", "並非", "并不是", "並不是", "不是", "并不", "並不", "非"})
_DEP_BARRIER_RELATIONS = frozenset({"ccomp", "advcl", "parataxis", "acl:relcl"})
_DEP_PARENT_NEGATION_RELATIONS = frozenset({"advmod", "aux", "cop"})


@dataclass
class NegationResult:
    """Result of negation detection for a symptom mention."""

    text: str
    symptom: str
    is_negated: bool
    negation_cue: str | None
    scope: str | None
    confidence: float


@dataclass(frozen=True)
class _CueMatch:
    text: str
    start: int
    end: int


class NegationDetector:
    """Scope-aware Chinese clinical negation detector."""

    _shared_nlp: Any | None = None
    _shared_nlp_failed = False

    def __init__(self, mode: str = "clause-rule"):
        """Initialize negation detector.

        Args:
            mode: "clause-rule" (default, no deps) or "stanza-dep" (requires stanza).
                  Crashes immediately if stanza-dep is requested but stanza is not installed.
        """
        if mode not in ("clause-rule", "stanza-dep"):
            raise ValueError(f"Invalid negation mode {mode!r}; expected 'clause-rule' or 'stanza-dep'")
        if mode == "stanza-dep":
            try:
                import stanza as _stanza  # noqa: F811
            except ImportError as e:
                raise ImportError(
                    "stanza is required for negation mode 'stanza-dep'. "
                    "Install with: pip install stanza"
                ) from e
        self.use_dep_parsing = mode == "stanza-dep"

    def detect(self, text: str, symptom: str) -> NegationResult:
        """Check if a symptom mention is negated in the given text."""
        result, _ = self._detect_impl(text, symptom, parsed_doc=None)
        return result

    def detect_batch(self, text: str, symptoms: list[str]) -> list[NegationResult]:
        """Check multiple symptoms against the same text."""
        parsed_doc = None
        results: list[NegationResult] = []
        for symptom in symptoms:
            result, parsed_doc = self._detect_impl(text, symptom, parsed_doc=parsed_doc)
            results.append(result)
        return results

    def _detect_impl(
        self,
        text: str,
        symptom: str,
        parsed_doc: Any | None,
    ) -> tuple[NegationResult, Any | None]:
        if not text or not symptom:
            return self._not_negated(text, symptom, confidence=0.0), parsed_doc

        symptom_positions = list(_find_all(text, symptom))
        if not symptom_positions:
            return self._not_negated(text, symptom, confidence=0.0), parsed_doc

        negated_candidates: list[NegationResult] = []
        for symptom_pos in symptom_positions:
            symptom_end = symptom_pos + len(symptom)
            if self._overlaps_positive_term(text, symptom_pos, symptom_end):
                return self._not_negated(text, symptom, confidence=0.96), parsed_doc

            occurrence_result, parsed_doc = self._detect_occurrence(
                text=text,
                symptom=symptom,
                symptom_pos=symptom_pos,
                symptom_end=symptom_end,
                parsed_doc=parsed_doc,
            )
            if occurrence_result is None:
                return self._not_negated(text, symptom, confidence=0.86), parsed_doc
            negated_candidates.append(occurrence_result)

        if negated_candidates:
            strongest = max(negated_candidates, key=lambda item: item.confidence)
            return strongest, parsed_doc

        return self._not_negated(text, symptom, confidence=0.86), parsed_doc

    def _detect_occurrence(
        self,
        *,
        text: str,
        symptom: str,
        symptom_pos: int,
        symptom_end: int,
        parsed_doc: Any | None,
    ) -> tuple[NegationResult | None, Any | None]:
        clause_start = self._previous_boundary(text, symptom_pos)
        candidate_cues = [
            cue
            for cue in self._iter_cues(text)
            if cue.end <= symptom_pos and cue.start >= clause_start
        ]
        candidate_cues.sort(key=lambda cue: cue.start, reverse=True)

        for cue in candidate_cues:
            scope_start, scope_end = self._resolve_scope(text, cue)
            if not (scope_start <= symptom_pos and symptom_end <= scope_end):
                continue
            if self._matches_exception(text, cue):
                continue
            if self._has_double_negation(text, clause_start, cue.start):
                return None, parsed_doc

            window = text[cue.end:symptom_pos]
            if self._requires_dep_verification(cue.text, window):
                dep_result, parsed_doc = self._check_dep_scope(
                    text=text,
                    cue=cue,
                    symptom_pos=symptom_pos,
                    symptom_end=symptom_end,
                    parsed_doc=parsed_doc,
                )
                if dep_result is False:
                    continue
                if dep_result is True:
                    return (
                        NegationResult(
                            text=text,
                            symptom=symptom,
                            is_negated=True,
                            negation_cue=cue.text,
                            scope=text[scope_start:scope_end],
                            confidence=min(self._rule_confidence(cue.text, window) + 0.08, 0.99),
                        ),
                        parsed_doc,
                    )

            return (
                NegationResult(
                    text=text,
                    symptom=symptom,
                    is_negated=True,
                    negation_cue=cue.text,
                    scope=text[scope_start:scope_end],
                    confidence=self._rule_confidence(cue.text, window),
                ),
                parsed_doc,
            )

        return None, parsed_doc

    def _resolve_scope(self, text: str, cue: _CueMatch) -> tuple[int, int]:
        """Find the scope of negation starting from the cue."""
        scope_end = len(text)
        next_delim = _DELIMITER_RE.search(text, cue.end)
        if next_delim is not None:
            scope_end = next_delim.start()
        if cue.text in {"无", "無", "未"}:
            breaker = _NOMINAL_SCOPE_BREAK_RE.search(text, cue.end, scope_end)
            if breaker is not None:
                scope_end = min(scope_end, breaker.start())
        return cue.start, scope_end

    def _previous_boundary(self, text: str, position: int) -> int:
        boundary = 0
        for match in _DELIMITER_RE.finditer(text):
            if match.start() >= position:
                break
            boundary = match.end()
        return boundary

    def _iter_cues(self, text: str) -> list[_CueMatch]:
        return [_CueMatch(match.group(0), match.start(), match.end()) for match in _CUE_RE.finditer(text)]

    def _matches_exception(self, text: str, cue: _CueMatch) -> bool:
        scope_start, scope_end = self._resolve_scope(text, cue)
        scope_text = text[scope_start:scope_end]
        for pattern in _EXCEPTION_RE:
            match = pattern.search(scope_text)
            if match is None:
                continue
            match_start = scope_start + match.start()
            match_end = scope_start + match.end()
            if match_start <= cue.start < match_end:
                return True
        return False

    def _has_double_negation(self, text: str, clause_start: int, cue_start: int) -> bool:
        prefix = text[clause_start:cue_start]
        return bool(_DOUBLE_NEGATION_PREFIX_RE.search(prefix))

    def _requires_dep_verification(self, cue_text: str, window: str) -> bool:
        return cue_text in {"无", "無", "未", "不", "没", "沒", "不是", "不太"} or len(window) >= 4

    def _check_dep_scope(
        self,
        *,
        text: str,
        cue: _CueMatch,
        symptom_pos: int,
        symptom_end: int,
        parsed_doc: Any | None,
    ) -> tuple[bool | None, Any | None]:
        doc = parsed_doc if parsed_doc is not None else self._get_doc(text)
        if doc is None:
            return None, parsed_doc

        for sentence in doc.sentences:
            words = {word.id: word for word in sentence.words}
            cue_words = [
                word
                for word in sentence.words
                if _span_overlaps(word.start_char, word.end_char, cue.start, cue.end)
            ]
            symptom_words = [
                word
                for word in sentence.words
                if _span_overlaps(word.start_char, word.end_char, symptom_pos, symptom_end)
            ]
            if not cue_words or not symptom_words:
                continue

            for cue_word in cue_words:
                if self._cue_has_negating_ancestor(cue_word, words):
                    return False, doc
                for symptom_word in symptom_words:
                    if self._cue_negates_word(cue_word, symptom_word, words):
                        return True, doc
            return False, doc

        return None, doc

    def _cue_has_negating_ancestor(self, cue_word: Any, words: dict[int, Any]) -> bool:
        current = cue_word
        while current.head:
            parent = words.get(current.head)
            if parent is None:
                break
            if parent.text in _DOUBLE_NEGATION_ANCESTORS or parent.lemma in _DOUBLE_NEGATION_ANCESTORS:
                return True
            current = parent
        return False

    def _cue_negates_word(self, cue_word: Any, symptom_word: Any, words: dict[int, Any]) -> bool:
        if cue_word.head == symptom_word.id and cue_word.deprel in _DEP_PARENT_NEGATION_RELATIONS:
            return True

        current = symptom_word
        while current.head:
            if current.deprel in _DEP_BARRIER_RELATIONS:
                return False
            parent = words.get(current.head)
            if parent is None:
                return False
            if parent.id == cue_word.id:
                return True
            current = parent
        return False

    def _get_doc(self, text: str) -> Any | None:
        if not self.use_dep_parsing:
            return None
        nlp = self._get_nlp()
        if nlp is None:
            return None
        return nlp(text)

    @classmethod
    def _get_nlp(cls) -> Any | None:
        if not cls._shared_nlp_failed and cls._shared_nlp is None:
            import stanza
            try:
                cls._shared_nlp = stanza.Pipeline(
                    "zh",
                    processors="tokenize,pos,lemma,depparse",
                    tokenize_no_ssplit=True,
                    verbose=False,
                )
            except Exception as exc:
                cls._shared_nlp_failed = True
                cls._shared_nlp = None
                raise RuntimeError(
                    "Failed to initialize stanza zh pipeline for negation mode 'stanza-dep'. "
                    "Ensure the stanza zh model is downloaded: python -c \"import stanza; stanza.download('zh')\""
                ) from exc
        return cls._shared_nlp

    def _overlaps_positive_term(self, text: str, symptom_pos: int, symptom_end: int) -> bool:
        for term in POSITIVE_NEGATION_TERMS:
            start = text.find(term)
            while start != -1:
                end = start + len(term)
                if start <= symptom_pos and symptom_end <= end:
                    return True
                start = text.find(term, start + 1)
        return False

    @staticmethod
    def _rule_confidence(cue_text: str, window: str) -> float:
        if cue_text in {"否认", "否認", "没有", "沒有"}:
            base = 0.94
        elif cue_text in {"无", "無", "未"}:
            base = 0.89
        else:
            base = 0.84
        if len(window) >= 4:
            base -= 0.08
        return max(base, 0.55)

    @staticmethod
    def _not_negated(text: str, symptom: str, confidence: float) -> NegationResult:
        return NegationResult(
            text=text,
            symptom=symptom,
            is_negated=False,
            negation_cue=None,
            scope=None,
            confidence=confidence,
        )


def _find_all(text: str, needle: str) -> list[int]:
    positions: list[int] = []
    start = 0
    while True:
        index = text.find(needle, start)
        if index == -1:
            return positions
        positions.append(index)
        start = index + 1


def _span_overlaps(left_start: int, left_end: int, right_start: int, right_end: int) -> bool:
    return left_start < right_end and right_start < left_end
