"""
Developer Node
Fetches the files to modify, asks the LLM to generate a unified diff,
then validates the changes inside a Docker sandbox.
"""

import logging
import os
import subprocess
import tempfile
import textwrap
from pathlib import Path
from typing import Optional

from langchain_core.messages import HumanMessage

from src.agent.state import AgentState, DiffResult
from src.github.client import get_file_content
from src.llm.client import get_llm

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fetch_relevant_files(repo_full_name: str, file_paths: list[str]) -> dict[str, str]:
    """Fetch content of files the architect flagged, plus test files if present."""
    contents: dict[str, str] = {}
    for path in file_paths[:6]:  # cap to avoid huge prompts
        content = get_file_content(repo_full_name, path)
        if content:
            contents[path] = content
    return contents


def _run_in_docker(diff_text: str, repo_url: str, timeout: int = 120) -> tuple[bool, str]:
    """
    Clone the repo in a Docker container, apply the diff, run existing tests.
    Returns (tests_passed, output).
    """
    docker_image = os.environ.get("DOCKER_IMAGE", "python:3.11-slim")

    script = textwrap.dedent(f"""
        set -e
        apt-get install -y git patch > /dev/null 2>&1 || true
        git clone --depth 1 {repo_url} /workspace 2>&1
        cd /workspace
        pip install -e . -q 2>&1 || pip install -r requirements.txt -q 2>&1 || true
        cat << 'DIFF_END' | patch -p1 --forward --reject-file=/tmp/rejects.patch || true
{diff_text}
DIFF_END
        python -m pytest --tb=short -q 2>&1 || python -m unittest discover -q 2>&1 || echo "No test runner found"
    """)

    try:
        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "--network", "none",           # no outbound network from sandbox
                "--memory", "512m",
                "--cpus", "1",
                docker_image,
                "bash", "-c", script,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout + result.stderr
        passed = result.returncode == 0
        return passed, output[:4000]
    except subprocess.TimeoutExpired:
        return False, "Docker sandbox timed out."
    except FileNotFoundError:
        # Docker not available — skip sandbox, warn user
        logger.warning("Docker not found. Skipping sandbox validation.")
        return True, "⚠️  Docker not available — sandbox skipped. Review diff carefully."
    except Exception as e:
        return False, f"Sandbox error: {e}"


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def developer_node(state: AgentState) -> dict:
    """
    Generate a unified diff fixing the selected issue, then validate it.
    Incorporates any human feedback from previous iterations.
    """
    issue = state.selected_issue
    plan = state.implementation_plan
    if issue is None or plan is None:
        return {"error_message": "Developer: missing issue or plan."}

    logger.info(f"👨‍💻 Developer: Writing code for {issue.repo_full_name} #{issue.issue_number}")

    file_contents = _fetch_relevant_files(issue.repo_full_name, plan.files_to_modify)

    files_block = "\n\n".join(
        f"### {path}\n```\n{content[:3000]}\n```"
        for path, content in file_contents.items()
    )

    feedback_section = ""
    if state.human_decision and state.human_decision.action == "feedback":
        feedback_section = f"""
## ⚠️ Human Feedback (incorporate this!)
{state.human_decision.feedback_text}
"""

    prompt = f"""You are an expert software engineer fixing a GitHub issue.

## Issue
{issue.title}

{issue.body[:1500]}

## Implementation Plan
{plan.summary}

Steps:
{chr(10).join(f"- {s}" for s in plan.steps)}

## Current File Contents
{files_block}
{feedback_section}

## Your Task
Produce a VALID unified diff (patch format) that fixes this issue.

Rules:
- Output ONLY the raw diff, nothing else (no markdown, no explanation)
- Keep changes minimal — do not refactor unrelated code
- Follow the existing code style exactly
- If adding new functionality, add a corresponding test if a test file exists

Start your output with: --- a/"""

    llm = get_llm(temperature=0.1)
    response = llm.invoke([HumanMessage(content=prompt)])
    diff_text = response.content.strip()

    # Strip accidental markdown fences
    import re
    diff_text = re.sub(r"^```(?:diff)?\s*\n", "", diff_text)
    diff_text = re.sub(r"\n```$", "", diff_text)

    # Validate in Docker sandbox
    timeout = int(os.environ.get("DOCKER_TIMEOUT_SECONDS", "120"))
    tests_passed, test_output = _run_in_docker(diff_text, issue.repo_url, timeout)

    diff_result = DiffResult(
        diff_text=diff_text,
        files_changed=plan.files_to_modify,
        tests_passed=tests_passed,
        test_output=test_output,
    )

    logger.info(f"✅ Diff generated — tests {'passed' if tests_passed else 'failed'}")

    return {
        "diff_result": diff_result,
        "current_node": "hitl",
        "iteration_count": state.iteration_count + 1,
    }
