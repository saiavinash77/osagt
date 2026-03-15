"""
Submitter Node
Only runs after human approval.
Forks the repo, pushes the diff on a new branch, and opens a PR.
"""

import logging
import os
import subprocess
import tempfile
from pathlib import Path

from github import Github

from src.agent.state import AgentState, PullRequest
from src.github.client import fork_repo, create_pull_request
from src.llm.client import get_llm
from langchain_core.messages import HumanMessage
from src.utils.email_sender import send_notification

logger = logging.getLogger(__name__)

PR_BODY_TEMPLATE = """## Summary
{summary}

## Changes
{files_changed}

## Testing
{test_status}

---
> 🤖 This PR was drafted by an AI agent and **reviewed + approved by a human** before submission.
> All changes were manually inspected prior to opening this pull request.
"""


def _generate_pr_title(issue_title: str, issue_number: int) -> str:
    """Generate a clean PR title from the issue."""
    llm = get_llm(temperature=0.3)
    response = llm.invoke([HumanMessage(content=
        f"Write a concise, conventional git commit-style PR title (max 72 chars) "
        f"for fixing this GitHub issue: '{issue_title}'. "
        f"Start with a verb (Fix, Add, Update, Refactor). No quotes, no issue number."
    )])
    return response.content.strip()


def _apply_diff_and_push(
    fork_clone_url: str,
    branch_name: str,
    diff_text: str,
    pr_title: str,
    github_token: str,
) -> bool:
    """Clone the fork, apply the diff, commit, and push."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Embed token in URL for authentication
        auth_url = fork_clone_url.replace(
            "https://github.com/",
            f"https://{github_token}@github.com/"
        )
        try:
            subprocess.run(["git", "clone", "--depth", "1", auth_url, tmpdir],
                           check=True, capture_output=True)
            subprocess.run(["git", "-C", tmpdir, "checkout", "-b", branch_name],
                           check=True, capture_output=True)

            # Write and apply diff
            diff_file = Path(tmpdir) / "changes.patch"
            diff_file.write_text(diff_text)
            apply_result = subprocess.run(
                ["git", "-C", tmpdir, "apply", "--whitespace=nowarn", str(diff_file)],
                capture_output=True, text=True
            )
            if apply_result.returncode != 0:
                logger.error(f"git apply failed: {apply_result.stderr}")
                return False

            subprocess.run(["git", "-C", tmpdir, "config", "user.email", "hitl-agent@users.noreply.github.com"],
                           check=True, capture_output=True)
            subprocess.run(["git", "-C", tmpdir, "config", "user.name", "HITL Contributor Bot"],
                           check=True, capture_output=True)
            subprocess.run(["git", "-C", tmpdir, "add", "-A"],
                           check=True, capture_output=True)
            subprocess.run(["git", "-C", tmpdir, "commit", "-m", pr_title],
                           check=True, capture_output=True)
            subprocess.run(["git", "-C", tmpdir, "push", "origin", branch_name],
                           check=True, capture_output=True)
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Git operation failed: {e.stderr}")
            return False


def submitter_node(state: AgentState) -> dict:
    """Fork the repo, push the approved diff, open a PR."""
    issue = state.selected_issue
    plan = state.implementation_plan
    diff_result = state.diff_result

    if not all([issue, plan, diff_result]):
        return {"error_message": "Submitter: missing issue, plan, or diff."}

    logger.info(f"🚀 Submitter: Opening PR for {issue.repo_full_name} #{issue.issue_number}")

    github_token = os.environ.get("GITHUB_TOKEN", "")
    g = Github(github_token)
    fork = fork_repo(issue.repo_full_name)
    fork_owner = g.get_user().login

    branch_name = f"hitl-fix-issue-{issue.issue_number}"
    pr_title = _generate_pr_title(issue.title, issue.issue_number)

    push_ok = _apply_diff_and_push(
        fork_clone_url=fork.clone_url,
        branch_name=branch_name,
        diff_text=diff_result.diff_text,
        pr_title=pr_title,
        github_token=github_token,
    )

    if not push_ok:
        return {"error_message": "Failed to push branch to fork. Check logs."}

    test_status = (
        "✅ Existing tests pass." if diff_result.tests_passed
        else "⚠️ Some tests failed — see diff notes."
    )
    files_changed_md = "\n".join(f"- `{f}`" for f in diff_result.files_changed)

    pr_data = create_pull_request(
        original_repo_full_name=issue.repo_full_name,
        fork_owner=fork_owner,
        branch_name=branch_name,
        title=pr_title,
        body=PR_BODY_TEMPLATE.format(
            summary=plan.summary,
            files_changed=files_changed_md,
            test_status=test_status,
        ),
    )

    pr = PullRequest(**pr_data)
    logger.info(f"🎉 PR opened: {pr.url}")
    
    send_notification(
        subject=f"Success! PR Opened for #{issue.issue_number}",
        body=f"The agent successfully opened a pull request for '{issue.title}'.\n\nView it here: {pr.url}"
    )

    return {
        "pull_request": pr,
        "current_node": "done",
    }
