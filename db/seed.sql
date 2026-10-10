-- Seed data: example rubrics for testing
-- Run after schema.sql

INSERT INTO rubrics (name, question_type, dimensions) VALUES
(
  'behavioral_star',
  'behavioral',
  '[
    {"name": "situation",    "description": "Clearly describes a specific, relevant situation",         "weight": 0.25},
    {"name": "task",         "description": "Explains the candidate''s role and responsibility",        "weight": 0.20},
    {"name": "action",       "description": "Details specific actions taken (not ''we'' but ''I'')",    "weight": 0.30},
    {"name": "result",       "description": "Quantifies or qualifies the outcome achieved",             "weight": 0.25}
  ]'::jsonb
),
(
  'technical_python',
  'technical',
  '[
    {"name": "correctness",  "description": "Solution is logically correct and handles edge cases",     "weight": 0.35},
    {"name": "complexity",   "description": "Demonstrates understanding of time/space complexity",      "weight": 0.25},
    {"name": "clarity",      "description": "Code is readable, well-named, and explained verbally",     "weight": 0.20},
    {"name": "depth",        "description": "Shows knowledge of Python idioms and stdlib",              "weight": 0.20}
  ]'::jsonb
),
(
  'leadership',
  'behavioral',
  '[
    {"name": "vision",       "description": "Articulates a clear direction or goal",                    "weight": 0.20},
    {"name": "influence",    "description": "Demonstrates persuasion or motivation of others",          "weight": 0.25},
    {"name": "decision",     "description": "Shows structured decision-making under uncertainty",       "weight": 0.30},
    {"name": "outcome",      "description": "Links leadership actions to measurable business impact",   "weight": 0.25}
  ]'::jsonb
)
ON CONFLICT (name) DO NOTHING;
