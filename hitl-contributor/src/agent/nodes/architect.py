"""
Architect Node
Analyses the selected issue + repo structure, then produces
a concrete, step-by-step implementation plan.
"""

import logging
from langchain_core.messages import HumanMessage

from src.agent.state import AgentState, ImplementationPlan
from src.github.client import get_repo_file_tree, get_file_content
from src.llm.client import get_llm

logger = logging.getLogger(__name__)


def architect_node(state: AgentState) -> dict:
    """
    Read the selected issue and relevant source files,
    then ask the LLM to create a structured implementation plan.
    """
    issue = state.selected_issue
    if issue is None:
        return {"error_message": "Architect: no issue selected."}

    logger.info(f"🏗️  Architect: Planning fix for {issue.repo_full_name} #{issue.issue_number}")

    # Gather repo context
    file_tree = get_repo_file_tree(issue.repo_full_name)
    tree_text = "\n".join(file_tree) if file_tree else "(could not fetch file tree)"

    # Try to fetch README for extra context
    readme_content = (
        get_file_content(issue.repo_full_name, "README.md")
        or get_file_content(issue.repo_full_name, "readme.md")
        or ""
    )[:1500]

    prompt = f"""You are a senior software engineer creating an implementation plan.

## Issue
Repository: {issue.repo_full_name}
Issue #{issue.issue_number}: {issue.title}

Description:
{issue.body[:2000]}

## Repository File Tree
{tree_text}

## README (first 1500 chars)
{readme_content}

## Your Task
Produce a JSON object with EXACTLY this structure (no markdown, raw JSON only):
{{
  "summary": "One paragraph explaining the root cause and your approach",
  "files_to_modify": ["path/to/file1.py", "path/to/file2.py"],
  "steps": [
    "Step 1: ...",
    "Step 2: ..."
  ],
  "estimated_complexity": "low" | "medium" | "high"
}}

Be specific about file paths. Keep steps actionable and atomic.
Output ONLY valid JSON."""

    llm = get_llm(temperature=0.1)
    response = llm.invoke([HumanMessage(content=prompt)])

    import json, re
    raw = response.content.strip()
    # Strip any accidental markdown fences
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        plan_data = json.loads(raw)
        plan = ImplementationPlan(**plan_data)
    except Exception as e:
        logger.error(f"Failed to parse architect response: {e}\nRaw: {raw}")
        return {"error_message": f"Architect output parse error: {e}"}

    logger.info(f"📋 Plan ready — complexity: {plan.estimated_complexity}, "
                f"files: {plan.files_to_modify}")

    return {
        "implementation_plan": plan,
        "current_node": "developer",
    }
