"""
test_feedback_engine.py
Wynisco AI Mock Interview Coach — Week 6 Capstone

Unit tests for feedback_engine.py helpers — no DB or API calls required.
Only tests the pure-logic helpers (prompt building, schema validation).
Run: pytest tests/ -v
"""

import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from feedback_engine import build_user_prompt, FEEDBACK_SCHEMA, SYSTEM_PROMPT


class TestBuildUserPrompt:

    def test_question_in_prompt(self):
        rubric = {"question_type": "behavioral", "dimensions": []}
        prompt = build_user_prompt("Tell me about a time you led a team.", "I led a project…", rubric)
        assert "Tell me about a time you led a team." in prompt

    def test_answer_in_prompt(self):
        rubric = {"question_type": "behavioral", "dimensions": []}
        prompt = build_user_prompt("Q?", "My specific answer here.", rubric)
        assert "My specific answer here." in prompt

    def test_rubric_type_in_prompt(self):
        rubric = {"question_type": "technical", "dimensions": [{"name": "correctness"}]}
        prompt = build_user_prompt("Q?", "A?", rubric)
        assert "technical" in prompt

    def test_dimensions_serialised_as_json(self):
        dims = [{"name": "situation", "weight": 0.25}]
        rubric = {"question_type": "behavioral", "dimensions": dims}
        prompt = build_user_prompt("Q?", "A?", rubric)
        # The dimensions should appear as JSON in the prompt
        assert "situation" in prompt
        assert "0.25" in prompt


class TestFeedbackSchema:

    def test_schema_has_required_fields(self):
        required = FEEDBACK_SCHEMA["required"]
        assert "clarity" in required
        assert "depth" in required
        assert "star_format" in required
        assert "red_flags" in required
        assert "suggestions" in required
        assert "summary" in required

    def test_clarity_bounds(self):
        clarity_schema = FEEDBACK_SCHEMA["properties"]["clarity"]
        assert clarity_schema["minimum"] == 1
        assert clarity_schema["maximum"] == 5

    def test_no_additional_properties(self):
        assert FEEDBACK_SCHEMA.get("additionalProperties") is False


class TestSystemPrompt:

    def test_system_prompt_not_empty(self):
        assert len(SYSTEM_PROMPT) > 50

    def test_system_prompt_mentions_json(self):
        assert "JSON" in SYSTEM_PROMPT

    def test_system_prompt_mentions_scoring(self):
        assert "1-5" in SYSTEM_PROMPT or "1 =" in SYSTEM_PROMPT
