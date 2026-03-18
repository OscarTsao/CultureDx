# tests/conftest.py
"""Shared test fixtures."""
import pytest
from pathlib import Path
from culturedx.core.models import Turn, ClinicalCase


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_case_zh():
    """A minimal Chinese clinical case for testing."""
    return ClinicalCase(
        case_id="test_zh_001",
        transcript=[
            Turn(speaker="doctor", text="你最近感觉怎么样?", turn_id=0),
            Turn(speaker="patient", text="我经常头疼，睡不着觉，心情很低落", turn_id=1),
            Turn(speaker="doctor", text="这种情况持续多久了?", turn_id=2),
            Turn(speaker="patient", text="大概两个多月了，每天都很难受", turn_id=3),
        ],
        language="zh",
        dataset="mdd5k",
        transcript_format="dialogue",
        coding_system="icd10",
        diagnoses=["F32"],
    )


@pytest.fixture
def sample_case_en():
    """A minimal English clinical case for testing."""
    return ClinicalCase(
        case_id="test_en_001",
        transcript=[
            Turn(speaker="interviewer", text="How have you been feeling?", turn_id=0),
            Turn(speaker="participant", text="Pretty bad, I can't sleep and I lost interest in everything", turn_id=1),
        ],
        language="en",
        dataset="edaic",
        transcript_format="dialogue",
        coding_system="dsm5",
        diagnoses=[],
        severity={"phq8_total": 16},
        metadata={"binary": 1},
    )
