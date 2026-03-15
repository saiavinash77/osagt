"""
Shared pytest fixtures and test environment setup.
Loaded automatically by pytest for all test files.
"""

import os
import pytest

# ── Set dummy env vars before any imports that read them ─────────────────────
os.environ.setdefault("OPENROUTER_API_KEY", "sk-or-test-dummy-key-for-ci")
os.environ.setdefault("GITHUB_TOKEN", "github_pat_test_dummy_token_for_ci")
os.environ.setdefault("GITHUB_USERNAME", "test-user")
os.environ.setdefault("ISSUE_LABELS", "good first issue")
os.environ.setdefault("LANGUAGE_FILTER", "python")
os.environ.setdefault("MAX_ISSUES_TO_SCAN", "3")
os.environ.setdefault("LLM_MODEL", "anthropic/claude-3.5-sonnet")
os.environ.setdefault("WEB_SECRET_KEY", "test-secret-key")
os.environ.setdefault("AUTO_RUN", "false")


# ── Shared fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def sample_issue_dict():
    return {
        "issue_number": 42,
        "title": "Fix typo in README",
        "body": "Line 3 has a typo: 'teh' should be 'the'.",
        "url": "https://github.com/owner/repo/issues/42",
        "repo_full_name": "owner/repo",
        "repo_url": "https://github.com/owner/repo",
        "labels": ["good first issue"],
        "language": "python",
    }


@pytest.fixture
def sample_plan_dict():
    return {
        "summary": "Correct the typo on line 3 of README.md",
        "files_to_modify": ["README.md"],
        "steps": ["Open README.md", "Fix typo on line 3", "Commit"],
        "estimated_complexity": "low",
    }


@pytest.fixture
def sample_diff_text():
    return (
        "--- a/README.md\n"
        "+++ b/README.md\n"
        "@@ -1,5 +1,5 @@\n"
        " # My Project\n"
        " \n"
        "-This is teh main readme.\n"
        "+This is the main readme.\n"
        " \n"
        " ## Install\n"
    )
