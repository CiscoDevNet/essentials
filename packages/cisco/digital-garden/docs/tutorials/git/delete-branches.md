---
title: Delete git branches
slug: /how-to-delete-git-branches
displayed_sidebar: snippetsSidebar
---

## Local branch

```sh
git branch -D ${BRANCH_NAME}
```

## Remote branch

```sh
git push -d origin ${BRANCH_NAME}
```

## References

1. https://stackoverflow.com/a/2003515/154065
