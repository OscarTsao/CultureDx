"""Tests for chief complaint integration in triage prompt."""
from __future__ import annotations

from jinja2 import Environment, FileSystemLoader


def _render(lang: str, **kwargs):
    """Render triage template with given variables."""
    env = Environment(
        loader=FileSystemLoader("prompts/agents"),
        keep_trailing_newline=True,
    )
    template = env.get_template(f"triage_{lang}.jinja")
    return template.render(**kwargs)


class TestTriageChiefComplaint:
    def test_zh_with_all_info(self):
        """Chinese template renders chief complaint and demographics."""
        rendered = _render(
            "zh",
            transcript_text="医生：你好",
            evidence_summary=None,
            chief_complaint="失眠、焦虑1月余",
            age=28,
            gender="女",
        )
        assert "主诉：失眠、焦虑1月余" in rendered
        assert "女，28岁" in rendered
        assert "患者基本信息" in rendered

    def test_zh_without_info(self):
        """Chinese template omits section when no info provided."""
        rendered = _render(
            "zh",
            transcript_text="医生：你好",
            evidence_summary=None,
            chief_complaint=None,
            age=None,
            gender=None,
        )
        assert "患者基本信息" not in rendered
        assert "主诉" not in rendered

    def test_en_with_chief_complaint(self):
        """English template renders chief complaint."""
        rendered = _render(
            "en",
            transcript_text="Doctor: Hello",
            evidence_summary=None,
            chief_complaint="insomnia and anxiety for 1 month",
            age=35,
            gender="Male",
        )
        assert "Chief complaint: insomnia" in rendered
        assert "Male, 35 years old" in rendered

    def test_en_without_info(self):
        """English template omits section when no info provided."""
        rendered = _render(
            "en",
            transcript_text="Doctor: Hello",
            evidence_summary=None,
            chief_complaint=None,
            age=None,
            gender=None,
        )
        assert "Patient Information" not in rendered
        assert "Chief complaint" not in rendered

    def test_json_output_still_at_end(self):
        """JSON output instructions are still the last section."""
        rendered = _render(
            "zh",
            transcript_text="...",
            evidence_summary=None,
            chief_complaint="头痛",
            age=40,
            gender="男",
        )
        # JSON output section should be after patient info and transcript
        json_pos = rendered.rfind("仅输出JSON")
        patient_pos = rendered.find("患者基本信息")
        transcript_pos = rendered.find("## 临床对话")
        assert json_pos > transcript_pos > patient_pos

    def test_partial_info_age_only(self):
        """Only age provided, no gender or chief complaint."""
        rendered = _render(
            "zh",
            transcript_text="...",
            evidence_summary=None,
            chief_complaint=None,
            age=30,
            gender=None,
        )
        assert "30岁" in rendered
        assert "患者基本信息" in rendered
        assert "主诉" not in rendered

    def test_partial_info_chief_complaint_only(self):
        """Only chief complaint, no demographics."""
        rendered = _render(
            "en",
            transcript_text="...",
            evidence_summary=None,
            chief_complaint="depression",
            age=None,
            gender=None,
        )
        assert "Chief complaint: depression" in rendered
        assert "Demographics" not in rendered
        assert "Age" not in rendered
