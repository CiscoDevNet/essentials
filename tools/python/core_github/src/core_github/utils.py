import pandas as pd

# Column constants
COLUMNS = [
    "Repo",
    "Title",
    "URL",
    "Lines added",
    "Lines deleted",
    "Lines changed",
    "Files changed",
    "Is mergeable",
]
COLUMNS_PRUNED = ["Repo", "URL", "Lines changed", "Files changed"]


def can_merge(merge_state_status):
    """
    Check if a PR can be merged based on mergeStateStatus.

    Args:
        merge_state_status: The mergeStateStatus value (string) - "CLEAN", "DIRTY", "UNSTABLE", etc.

    Returns:
        bool: True if mergeStateStatus is "CLEAN", False otherwise
    """
    return merge_state_status == "CLEAN"


def format_pr_dataframe(pr_data):
    """
    Format PR data into a pandas DataFrame and display it.

    Args:
        pr_data: List of lists containing PR data in format:
                 [repo_name, title, url, lines_added, lines_deleted, lines_changed, changed_files, is_mergeable]

    Returns:
        pandas.DataFrame: Sorted DataFrame with PR information
    """
    if not pr_data:
        return pd.DataFrame()

    df = pd.DataFrame(pr_data, columns=COLUMNS)
    df_sorted = df.sort_values("Lines changed")

    df_pruned = df_sorted[COLUMNS_PRUNED]

    # Do not truncate the URL so that we can click it.
    pd.set_option("display.max_colwidth", None)

    return df_pruned
