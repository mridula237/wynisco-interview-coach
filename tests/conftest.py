"""
conftest.py — shared fixtures for pytest
No database or OpenAI calls; all tests are pure-unit.
"""

import pytest


@pytest.fixture
def behavioral_rubric_dims():
    return [
        {"name": "situation",  "description": "Clearly describes a specific, relevant situation", "weight": 0.25},
        {"name": "task",       "description": "Explains the candidate's role and responsibility",  "weight": 0.20},
        {"name": "action",     "description": "Details specific actions taken (not 'we' but 'I')", "weight": 0.30},
        {"name": "result",     "description": "Quantifies or qualifies the outcome achieved",      "weight": 0.25},
    ]


@pytest.fixture
def good_feedback():
    """Feedback that should pass all eval checks."""
    return {
        "clarity":     4,
        "depth":       4,
        "star_format": 4,
        "summary": (
            "The candidate clearly described the situation and task, "
            "then explained the specific action they took individually, "
            "and quantified the result with a 20% improvement metric."
        ),
        "suggestions": [
            "Try to quantify the result more specifically — add the actual metric.",
            "Use 'I' instead of 'we' when describing the action step.",
            "Structure the situation section to include the business context.",
            "Include the timeline to give the result more impact.",
        ],
        "red_flags": [
            "Answer uses 'we' throughout — unclear what the candidate did individually.",
        ],
    }


@pytest.fixture
def weak_feedback():
    """Feedback with vague suggestions that should fail actionability."""
    return {
        "clarity":     2,
        "depth":       2,
        "star_format": 2,
        "summary": "The answer was unclear and lacked structure.",
        "suggestions": [
            "The answer could be better.",
            "More detail would help.",
        ],
        "red_flags": ["No specific outcome mentioned."],
    }
