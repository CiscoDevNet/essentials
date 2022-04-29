---
id: squash-commits
title: Squash git commits
slug: /how-to-squash-git-commits
displayed_sidebar: snippetsSidebar
---

```sh
git checkout ${BRANCH_TO_SQUASH}
```

For safety, let’s tag the current commit.

```sh
git tag ${MY_LOCAL_BRANCH_BACKUP}
```

:::tip

If the tag exists from a prior backup, and you no longer need it, delete it.

`git tag --delete ${MY_LOCAL_BRANCH_BACKUP}`

:::

Next, move the branch `HEAD` back to your last "good commit", the commit on your branch that you want to keep.

```sh
git reset --soft <last-good-commit>
```

Using `git status`, you'll notice that all changes on your feature branch are now staged.  All that's left to do is ...

```sh
git commit
```
