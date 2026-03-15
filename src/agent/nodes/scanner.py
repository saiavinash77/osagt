"""
Scanner Node
Searches GitHub for beginner-friendly issues and picks the best one
for the agent to attempt.
"""

import os
import logging
from src.agent.state import AgentState, GithubIssue
from src.github.client import search_good_first_issues
from src.llm.client import get_llm
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)


def scanner_node(state: AgentState) -> dict:
    """
    1. Search GitHub for matching issues.
    2. Use the LLM to rank/select the most tractable one.
    3. Return updated state with selected_issue set.
    """
    logger.info("🔍 Scanner: Searching for issues...")

    labels_raw = os.environ.get("ISSUE_LABELS", "good first issue,help wanted")
    labels = [lbl.strip() for lbl in labels_raw.split(",")]

    languages_raw = os.environ.get("LANGUAGE_FILTER", "python")
    languages = [lang.strip() for lang in languages_raw.split(",")]

    domains_raw = os.environ.get("TARGET_DOMAINS", "")
    topics = [domain.strip() for domain in domains_raw.split(",")] if domains_raw else []

    max_issues = int(os.environ.get("MAX_ISSUES_TO_SCAN", "5"))

    raw_issues = search_good_first_issues(
        labels=labels,
        languages=languages,
        topics=topics,
        max_results=max_issues,
    )

    if not raw_issues:
        logger.warning("No issues found. Try broadening LANGUAGE_FILTER or ISSUE_LABELS.")
        return {"error_message": "No suitable issues found on GitHub."}

    issues = [GithubIssue(**i) for i in raw_issues]

    # Ask the LLM to pick the best issue (most self-contained, lowest risk)
    issue_list_text = "\n\n".join(
        f"[{idx}] {iss.repo_full_name} #{iss.issue_number}\n"
        f"Title: {iss.title}\n"
        f"Labels: {', '.join(iss.labels)}\n"
        f"Body preview: {iss.body[:300]}..."
        for idx, iss in enumerate(issues)
    )

    prompt = f"""You are helping select the best GitHub issue for an automated agent to fix.
Choose the issue that is:
- Most self-contained (minimal external dependencies)
- Clearly described (not vague)
- Realistic to fix in a single PR (bug fix, typo, small feature, missing test)
- Lowest risk of being rejected by maintainers

Issues to evaluate:
{issue_list_text}

Reply with ONLY the index number (0-{len(issues)-1}) of the best issue. No explanation."""

    llm = get_llm()
    response = llm.invoke([HumanMessage(content=prompt)])
    
    try:
        chosen_idx = int(response.content.strip())
        selected = issues[chosen_idx]
    except (ValueError, IndexError):
        logger.warning("LLM gave unexpected index, defaulting to first issue.")
        selected = issues[0]

    logger.info(f"✅ Selected: {selected.repo_full_name} #{selected.issue_number} — {selected.title}")

    return {
        "candidate_issues": issues,
        "selected_issue": selected,
        "current_node": "architect",
    }
