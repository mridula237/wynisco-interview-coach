"""
test_eval_layer.py
Wynisco AI Mock Interview Coach — Week 6 Capstone

Unit tests for eval_layer.py — no DB or API calls required.
Run: pytest tests/ -v
"""

import sys
import os

# Allow import of app/ modules without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from eval_layer import (
    score_rubric_coverage,
    score_actionability,
    redact_pii,
    RUBRIC_COVERAGE_THRESHOLD,
    ACTIONABILITY_THRESHOLD,
)


# ---------------------------------------------------------------------------
# 1. Rubric Coverage  (Week 5: Faithfulness)
# ---------------------------------------------------------------------------

class TestRubricCoverage:

    def test_full_coverage_passes(self, good_feedback, behavioral_rubric_dims):
        """All 4 STAR dimensions mentioned in feedback → score ≥ threshold."""
        score = score_rubric_coverage(good_feedback, behavioral_rubric_dims)
        assert score >= RUBRIC_COVERAGE_THRESHOLD, (
            f"Expected ≥ {RUBRIC_COVERAGE_THRESHOLD}, got {score}"
        )

    def test_empty_rubric_returns_one(self, good_feedback):
        """No dimensions defined → score = 1.0 (nothing to miss)."""
        score = score_rubric_coverage(good_feedback, [])
        assert score == 1.0

    def test_no_dimensions_mentioned_returns_zero(self, behavioral_rubric_dims):
        """Feedback with no dimension keywords → score = 0."""
        blank_feedback = {
            "summary": "Good job overall.",
            "suggestions": ["Keep it up."],
            "red_flags": [],
        }
        score = score_rubric_coverage(blank_feedback, behavioral_rubric_dims)
        assert score == 0.0

    def test_partial_coverage_below_threshold(self, behavioral_rubric_dims):
        """Only 1 of 4 dimensions mentioned → score = 0.25, below threshold."""
        partial_feedback = {
            "summary": "The candidate described the situation well.",
            "suggestions": [],
            "red_flags": [],
        }
        score = score_rubric_coverage(partial_feedback, behavioral_rubric_dims)
        assert score < RUBRIC_COVERAGE_THRESHOLD

    def test_score_is_between_zero_and_one(self, good_feedback, behavioral_rubric_dims):
        score = score_rubric_coverage(good_feedback, behavioral_rubric_dims)
        assert 0.0 <= score <= 1.0

    def test_score_is_rounded_to_3dp(self, good_feedback, behavioral_rubric_dims):
        score = score_rubric_coverage(good_feedback, behavioral_rubric_dims)
        assert score == round(score, 3)


# ---------------------------------------------------------------------------
# 2. Actionability  (Week 5: Answer Relevance)
# ---------------------------------------------------------------------------

class TestActionability:

    def test_actionable_suggestions_pass(self, good_feedback):
        """Suggestions with concrete verbs → score ≥ threshold."""
        score = score_actionability(good_feedback)
        assert score >= ACTIONABILITY_THRESHOLD, (
            f"Expected ≥ {ACTIONABILITY_THRESHOLD}, got {score}"
        )

    def test_vague_suggestions_fail(self, weak_feedback):
        """Vague suggestions with no action verbs → score < threshold."""
        score = score_actionability(weak_feedback)
        assert score < ACTIONABILITY_THRESHOLD

    def test_no_suggestions_returns_zero(self):
        feedback_no_sugs = {"suggestions": []}
        score = score_actionability(feedback_no_sugs)
        assert score == 0.0

    def test_missing_suggestions_key_returns_zero(self):
        score = score_actionability({})
        assert score == 0.0

    def test_all_actionable_returns_one(self):
        feedback = {
            "suggestions": [
                "Use the STAR framework to structure your answer.",
                "Include a specific metric to quantify the result.",
                "Avoid using 'we' — describe your individual contribution.",
            ]
        }
        score = score_actionability(feedback)
        assert score == 1.0

    def test_score_between_zero_and_one(self, good_feedback):
        score = score_actionability(good_feedback)
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# 3. PII Guardrail  (reused from Week 5)
# ---------------------------------------------------------------------------

class TestPIIRedaction:

    def test_email_is_redacted(self):
        text = "Contact me at john.doe@example.com for follow-up."
        redacted, detected = redact_pii(text)
        assert detected is True
        assert "john.doe@example.com" not in redacted

    def test_phone_is_redacted(self):
        text = "Call me at 555-123-4567 anytime."
        redacted, detected = redact_pii(text)
        assert detected is True
        assert "555-123-4567" not in redacted

    def test_ssn_is_redacted(self):
        text = "My SSN is 123-45-6789."
        redacted, detected = redact_pii(text)
        assert detected is True
        assert "123-45-6789" not in redacted

    def test_clean_text_unchanged(self):
        text = "I led a team of five engineers to deliver the project on time."
        redacted, detected = redact_pii(text)
        assert detected is False
        assert redacted == text

    def test_multiple_pii_types_all_redacted(self):
        text = "Email: jane@work.com, Phone: 800-555-0199"
        redacted, detected = redact_pii(text)
        assert detected is True
        assert "jane@work.com" not in redacted
        assert "800-555-0199" not in redacted

    def test_returns_tuple_of_str_and_bool(self):
        result = redact_pii("some text")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], bool)

    def test_empty_string(self):
        redacted, detected = redact_pii("")
        assert redacted == ""
        assert detected is False
