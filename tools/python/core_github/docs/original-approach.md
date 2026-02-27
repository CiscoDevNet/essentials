```python
import pandas as pd
from decouple import config
from github import Github

GH_TOKEN = config("GH_PAT")
GH_HOSTNAME = config("GH_HOSTNAME")
GH_USERNAME = config("GH_USERNAME")
GH_ORG = config("GH_ORG")


def get_prs(username=GH_USERNAME):
    print(f"GitHub hostname: {GH_HOSTNAME}")

    base_url = f"https://{GH_HOSTNAME}/api/v3"
    gh = Github(base_url=base_url, login_or_token=GH_TOKEN)

    org = gh.get_organization(GH_ORG)
    requested_count = 0
    pr_data = []

    # for repo in gh_client.get_user().get_repos():
    for repo in org.get_repos():
        prs = repo.get_pulls(state="open")
        for pr in prs:
            is_reviewer = any(
                review.login == username for review in pr.get_review_requests()[0]
            )
            is_approved = any(
                review.user.login == username and review.state == "APPROVED"
                for review in pr.get_reviews()
            )

            if not is_approved and is_reviewer:
                requested_count += 1
                print(f"{requested_count}. {repo.name}: {pr.title}")

                lines_added = pr.additions
                lines_deleted = pr.deletions
                lines_changed = lines_added + lines_deleted

                pr_data.append(
                    [
                        repo.name,
                        pr.title,
                        pr.html_url,
                        lines_added,
                        lines_deleted,
                        lines_changed,
                    ]
                )

    # TODO: Make these strings constants.
    COLUMNS = ["Repo", "Title", "URL", "Lines added", "Lines deleted", "Lines changed"]
    df = pd.DataFrame(pr_data, columns=COLUMNS)
    df_sorted = df.sort_values("Lines changed")

    print(f"PRs requested: {len(df)}")

    COLUMNS_PRUNED = ["Repo", "URL", "Lines changed"]
    # Do not show row indexes.
    df_pruned = df_sorted[COLUMNS_PRUNED].to_string(index=False)

    # Do not truncate the URL so that we can click it.
    pd.set_option("display.max_colwidth", None)
    print(df_pruned)
```
