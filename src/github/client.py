"""
GitHub API client built on PyGithub.
Handles issue searching, repo cloning, forking, and PR creation.
"""

import os
import logging
from functools import lru_cache
from typing import List, Optional

from github import Github, GithubException
from github.Repository import Repository
from github.Issue import Issue

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_github_client() -> Github:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise EnvironmentError("GITHUB_TOKEN not set in environment.")
    return Github(token)


# ---------------------------------------------------------------------------
# Issue scanning
# ---------------------------------------------------------------------------

def search_good_first_issues(
    labels: List[str],
    languages: List[str],
    topics: Optional[List[str]] = None,
    max_results: int = 5,
) -> List[dict]:
    """
    Search GitHub for open issues matching given labels, languages, and topics.
    Returns a list of raw issue dicts ready to be converted to GithubIssue.
    """
    g = get_github_client()
    results = []
    topics = topics or []

    for language in languages:
        label_query = " ".join(f'label:"{lbl}"' for lbl in labels)
        
        # If topics are provided, we search for each topic to get a good mix
        topics_to_search = topics if topics else [""]
        
        for topic in topics_to_search:
            topic_str = f" {topic}" if topic else ""
            query = f"{label_query} language:{language}{topic_str} state:open is:issue no:assignee"

            logger.info(f"Searching GitHub: {query}")
        try:
            issues = g.search_issues(query=query, sort="created", order="desc")
            for issue in issues[:max_results]:
                repo = issue.repository
                results.append({
                    "issue_number": issue.number,
                    "title": issue.title,
                    "body": issue.body or "",
                    "url": issue.html_url,
                    "repo_full_name": repo.full_name,
                    "repo_url": repo.html_url,
                    "labels": [lbl.name for lbl in issue.labels],
                    "language": language,
                })
        except GithubException as e:
            logger.error(f"GitHub search failed: {e}")

    return results[:max_results]


# ---------------------------------------------------------------------------
# Repository helpers
# ---------------------------------------------------------------------------

def get_repo(repo_full_name: str) -> Repository:
    g = get_github_client()
    return g.get_repo(repo_full_name)


def get_repo_file_tree(repo_full_name: str, max_files: int = 60) -> List[str]:
    """Return a flat list of file paths in the repo (for architect context)."""
    repo = get_repo(repo_full_name)
    try:
        contents = repo.get_git_tree(sha="HEAD", recursive=True)
        paths = [item.path for item in contents.tree if item.type == "blob"]
        return paths[:max_files]
    except GithubException as e:
        logger.warning(f"Could not fetch file tree for {repo_full_name}: {e}")
        return []


def get_file_content(repo_full_name: str, file_path: str) -> Optional[str]:
    """Fetch raw content of a single file from GitHub."""
    repo = get_repo(repo_full_name)
    try:
        content_file = repo.get_contents(file_path)
        return content_file.decoded_content.decode("utf-8", errors="replace")
    except GithubException as e:
        logger.warning(f"Could not fetch {file_path} from {repo_full_name}: {e}")
        return None


# ---------------------------------------------------------------------------
# Forking & PR
# ---------------------------------------------------------------------------

def fork_repo(repo_full_name: str) -> Repository:
    """Fork a repo to the authenticated user's account."""
    g = get_github_client()
    repo = g.get_repo(repo_full_name)
    user = g.get_user()
    logger.info(f"Forking {repo_full_name} to {user.login}...")
    return user.create_fork(repo)


def create_pull_request(
    original_repo_full_name: str,
    fork_owner: str,
    branch_name: str,
    title: str,
    body: str,
) -> dict:
    """Open a PR from fork_owner:branch_name → original_repo default branch."""
    g = get_github_client()
    original_repo = g.get_repo(original_repo_full_name)
    default_branch = original_repo.default_branch

    pr = original_repo.create_pull(
        title=title,
        body=body,
        head=f"{fork_owner}:{branch_name}",
        base=default_branch,
    )
    logger.info(f"PR created: {pr.html_url}")
    return {
        "url": pr.html_url,
        "number": pr.number,
        "title": pr.title,
        "branch_name": branch_name,
    }
