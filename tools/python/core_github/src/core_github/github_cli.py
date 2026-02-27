import json
import logging
import subprocess

from decouple import config

from .utils import can_merge, format_pr_dataframe

logger = logging.getLogger(__name__)

# Configure logging level based on DEBUG environment variable
# Maps string names to logging level constants
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}
LOG_LEVEL = config("LOG_LEVEL", default="WARNING")
log_level = LOG_LEVELS.get(LOG_LEVEL.upper(), logging.WARNING)
logging.basicConfig(level=log_level)


def _get_author_query(authors: list[str] | str | None):
    """
    Build author query string for GitHub CLI search.

    Args:
        authors: PR author filter - None (no author filter), string or list of strings.
                 Multiple authors will be combined with OR syntax.

    Returns:
        str: Author query string, or empty string if authors is None
    """
    if authors is not None:
        # Normalize authors to a list
        if isinstance(authors, str):
            authors_list = [authors]
        else:
            authors_list = authors
        return " OR ".join(f"author:{author}" for author in authors_list)
    return ""


def _get_draft_query(draft_status):
    """
    Build draft query string for GitHub CLI search.

    Args:
        draft_status: Draft filter - None (include both), False (exclude drafts),
                      or True (only drafts)

    Returns:
        str: Draft query string, or empty string if draft_status is None
    """
    if draft_status is True:
        return "draft:true"
    elif draft_status is False:
        return "draft:false"
    return ""


def _get_mergeable_query(is_mergeable):
    """
    Build mergeable query string for GitHub CLI search.

    Args:
        is_mergeable: Mergeable filter - None (include all), True (only mergeable with
                      mergeableState == "clean"), False (only PRs with conflicts or failing checks:
                      mergeableState == "dirty" OR "unstable")

    Returns:
        str: Mergeable query string, or empty string if is_mergeable is None
    """
    if is_mergeable is True:
        return "mergeableState:clean"
    elif is_mergeable is False:
        return "(mergeableState:dirty OR mergeableState:unstable)"
    return ""


def _build_pr_query_base(
    author: str | None = None,
    state: str = "all",
    limit: int | None = None,
    draft_status: bool | None = None,
    is_mergeable: bool | None = None,
):
    """
    Build the base command list for PR queries using GitHub CLI.

    Args:
        author: PR author filter - None (no author filter) or single author string.
                For multiple authors, caller should query separately and combine results.
        state: PR state filter - "all", "open", "closed", or "merged" (default: "all")
        limit: Maximum number of PRs to retrieve (default: None). If None, GitHub CLI defaults to 30.
        draft_status: Draft filter - None (default, include both), False (exclude drafts),
                      or True (only drafts)
        is_mergeable: Mergeable filter - None (default, include all), True (only mergeable with
                      mergeableState == "clean"), False (only PRs with conflicts or failing checks:
                      mergeableState == "dirty" OR "unstable")

    Returns:
        list: Base command list for gh pr list queries
    """
    # Build search query for non-author filters
    query_parts = [
        _get_draft_query(draft_status),
        _get_mergeable_query(is_mergeable),
    ]
    search_query = " ".join(part for part in query_parts if part).strip()

    cmd = [
        "gh",
        "pr",
        "list",
        "--state",
        state,
        "--json",
        "number,title,author,url,createdAt,state,isDraft,changedFiles,additions,deletions,mergeStateStatus",
    ]

    # Use --author flag for single author (more efficient than --search)
    if author:
        cmd.extend(["--author", author])

    # Add --search if we have other filters
    if search_query:
        cmd.extend(["--search", search_query])

    if limit is not None:
        cmd.extend(["--limit", str(limit)])
    return cmd


def prs_data_to_dataframe(prs_data, org_repo):
    """
    Process PR data from GitHub CLI JSON output and convert to DataFrame.

    Args:
        prs_data: List of PR dictionaries from GitHub CLI JSON output
        org_repo: Repository in format "org/repo" (e.g., "Cisco-DES/aide")

    Returns:
        pandas.DataFrame: DataFrame with PR information
    """
    # Extract repo name from org_repo
    _, _, repo_name = org_repo.partition("/")

    pr_data = []
    for pr in prs_data:
        lines_added = pr.get("additions", 0)
        lines_deleted = pr.get("deletions", 0)
        lines_changed = lines_added + lines_deleted
        changed_files = pr.get("changedFiles", 0)
        is_mergeable = can_merge(pr.get("mergeStateStatus", "UNKNOWN"))

        pr_data.append(
            [
                repo_name,
                pr.get("title", ""),
                pr.get("url", ""),
                lines_added,
                lines_deleted,
                lines_changed,
                changed_files,
                is_mergeable,
            ]
        )

    return format_pr_dataframe(pr_data)


def get_prs(
    org_repo="Cisco-DES/aide",
    authors=None,
    state="all",
    limit=None,
    draft_status=None,
    is_mergeable=None,
):
    """
    Get PRs for a particular org/repo using GitHub CLI.

    Args:
        org_repo: Repository in format "org/repo" (e.g., "Cisco-DES/aide")
        authors: PR author filter - None (default, no author filter), string or list of strings.
                 Multiple authors will be queried separately and results combined.
        state: PR state filter - "all", "open", "closed", or "merged" (default: "all")
        limit: Maximum number of PRs to retrieve (default: None). If None, GitHub CLI defaults to 30.
        draft_status: Draft filter - None (default, include both), False (exclude drafts),
                      or True (only drafts)
        is_mergeable: Mergeable filter - None (default, include all), True (only mergeable with
                      mergeableState == "clean"), False (only PRs with conflicts or failing checks:
                      mergeableState == "dirty" OR "unstable")

    Returns:
        list: List of PR dictionaries from GitHub CLI JSON output
    """
    # Normalize authors to a list (empty list if None)
    if authors is None:
        authors_list = []
    elif isinstance(authors, str):
        authors_list = [authors]
    else:
        authors_list = authors

    # If no authors, query once without author filter
    # If one or more authors, loop through each and combine results
    all_prs = []
    seen_numbers = set()

    # Create list of authors to query (empty list means query once without author filter)
    authors_to_query = authors_list if authors_list else [None]

    for author in authors_to_query:
        # Build command for this author (None means no author filter)
        cmd = _build_pr_query_base(author, state, limit, draft_status, is_mergeable)
        cmd.extend(["-R", org_repo])

        logger.debug("Running command: %s", " ".join(cmd))

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True, timeout=30
            )
            prs_data = json.loads(result.stdout)

            # Add PRs we haven't seen yet (deduplicate by PR number)
            for pr in prs_data:
                pr_number = pr.get("number")
                if pr_number and pr_number not in seen_numbers:
                    seen_numbers.add(pr_number)
                    all_prs.append(pr)

        except subprocess.CalledProcessError as e:
            author_str = author if author else "no author filter"
            logger.error(
                "Error running gh CLI command for author %s: %s", author_str, e
            )
            logger.error("stderr: %s", e.stderr)
        except json.JSONDecodeError as e:
            author_str = author if author else "no author filter"
            logger.error("Error parsing JSON output for author %s: %s", author_str, e)
        except FileNotFoundError:
            logger.error("Error: GitHub CLI (gh) not found. Please install it first.")
            return []

    # Sort by PR number descending (most recent first)
    all_prs.sort(key=lambda x: x.get("number", 0), reverse=True)

    # Apply limit if specified
    if limit is not None and len(all_prs) > limit:
        all_prs = all_prs[:limit]

    return all_prs
