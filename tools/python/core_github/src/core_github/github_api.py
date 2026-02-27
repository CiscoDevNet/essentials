import logging
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Lock

from github import Auth, Github

logger = logging.getLogger(__name__)


class GitHubCore:
    """GitHub API client for interacting with GitHub repositories and pull requests."""

    def __init__(self, token: str):
        """
        Initialize GitHubCore with a GitHub token.

        Args:
            token: GitHub personal access token for authentication
        """
        auth = Auth.Token(token)
        self.gh = Github(auth=auth)

    def get_prs(self):
        """
        Retrieve all open pull requests across all repositories the authenticated user has access to.
        Uses search API to find PRs you're involved with (avoids SAML issues with org iteration).
        Yields PRs as they are discovered.

        Yields:
            PullRequest: GitHub pull request object
        """
        processed_prs = set()
        processed_repos = set()
        lock = Lock()
        pr_queue = Queue()

        # Get username upfront
        username = self.gh.get_user().login

        def process_user_repos():
            """Process repos the user directly owns or has access to."""
            try:
                for repo in self.gh.get_user().get_repos():
                    for pr in self._process_repo_prs(
                        repo, processed_repos, processed_prs, lock
                    ):
                        pr_queue.put(pr)
            except Exception as e:
                logger.debug("Error processing user repos: %s", e)

        def process_search_prs(query_name, query):
            """Search for PRs using a search query."""
            logger.debug("Searching PRs: %s -> %s", query_name, query)
            try:
                issues = self.gh.search_issues(query=query)
                for issue in issues:
                    pr = issue.as_pull_request()
                    with lock:
                        pr_id = pr.html_url
                        if pr_id in processed_prs:
                            continue
                        processed_prs.add(pr_id)
                    logger.debug("  [%s] %s", query_name, pr.html_url)
                    pr_queue.put(pr)
            except Exception as e:
                logger.debug("Search failed for %s: %s", query_name, e)

        # Search queries for various ways user might be involved with PRs
        search_queries = [
            ("review-requested", f"is:pr is:open review-requested:{username}"),
            ("involves", f"is:pr is:open involves:{username}"),
            ("author", f"is:pr is:open author:{username}"),
            ("assignee", f"is:pr is:open assignee:{username}"),
        ]

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_user_repos)]
            for query_name, query in search_queries:
                futures.append(executor.submit(process_search_prs, query_name, query))

            # Yield PRs as they come in while threads are running
            while any(not f.done() for f in futures) or not pr_queue.empty():
                try:
                    pr = pr_queue.get(timeout=0.1)
                    yield pr
                except Exception:
                    pass

            # Check for exceptions (they're already caught inside, so this is just cleanup)
            for future in futures:
                try:
                    future.result()
                except Exception:
                    pass

    def _process_repo_prs(self, repo, processed_repos, processed_prs, lock):
        """
        Process all open pull requests for a given repository.
        Yields each PR if the repository hasn't been processed yet.

        Args:
            repo: GitHub repository object
            processed_repos: Set of already processed repo full names
            processed_prs: Set of already processed PR URLs
            lock: Threading lock for thread-safe set access

        Yields:
            PullRequest: GitHub pull request object
        """
        repo_name = repo.full_name

        # Mark repo as processed immediately to prevent duplicate processing
        with lock:
            if repo_name in processed_repos:
                return
            processed_repos.add(repo_name)

        prs = repo.get_pulls(state="open")
        for pr in prs:
            with lock:
                pr_id = pr.html_url
                if pr_id in processed_prs:
                    continue
                processed_prs.add(pr_id)
            yield pr
