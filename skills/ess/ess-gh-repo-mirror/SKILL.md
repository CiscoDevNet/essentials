---
name: ess-gh-repo-mirror
description: >-
  Mirror a GitHub repo or GitHub Action, including its tags, into another GitHub
  owner or org, or sync an existing mirror. Use when asked to mirror, fork, copy,
  or sync a repo or action into another org, or when a workflow cannot use an
  Action from outside its own org.
license: Apache-2.0
compatibility: >-
  Requires git and an authenticated gh CLI with permission to create repos in the
  target owner. GitHub only.
---

# Mirror a GitHub Repo

Copy a GitHub repo's default branch and all of its tags into a repo under another owner or
org, and keep that copy in sync with the source.

This is most useful for GitHub Actions. Orgs often restrict workflows to Actions hosted in
the org itself, so a workflow cannot reference `some-org/some-action@v4` directly. Mirroring
copies the versions you want into your own org, and workflows reference the mirror instead,
for example `your-org/some-action@v4`. Because tags come along, existing version pins keep
working after you swap the owner.

## Inputs

| Input | Format | Default |
| ----- | ------ | ------- |
| Source | `https://github.com/<org>/<repo>` or `<org>/<repo>` | Required |
| Target | `<owner>` or `<owner>/<name>` | Required; ask if not given. Name defaults to the source repo name. |
| Visibility | `private`, `internal`, or `public` | `private` |
| Remote | Git remote name for the target | The target owner |

`private` is the tightest visibility: only people explicitly granted access can read the repo.
`internal` makes it readable by every member of the enterprise and exists only for orgs on
GitHub Enterprise. Use a looser visibility only when the user asks for it.

## Workflow

### 1. Clone the source (skip if already present)

```bash
git clone https://github.com/<org>/<repo>.git
cd <repo>
```

Clone next to the current repo unless the user names another location.

### 2. Confirm before writing anything remote

Check whether the target exists:

```bash
gh repo view <owner>/<name> --json visibility 2>/dev/null
```

Then show the user a summary and wait for an explicit yes:

- Source `<org>/<repo>` and its default branch
- Target `<owner>/<name>`, and whether it will be created or already exists
- Visibility (for an existing repo, its current visibility)
- Remote name
- For an Action: the repos whose workflows will use it, and the access level that lets them
  (work these out as described in step 7)

Stop on anything but yes.

### 3. Create the target repo (skip if it exists)

```bash
gh repo create <owner>/<name> --<visibility>
```

### 4. Add the target remote

Reuse a remote that already points at the target (`git remote -v`); otherwise add one:

```bash
git remote add <remote> https://github.com/<owner>/<name>.git
```

### 5. Push the default branch and the source's tags

Push the upstream default branch and the source's tags. A reused clone may be on a feature
branch, carry local-only commits or tags, or be detached. Do not push the current checkout,
and do not push `refs/tags/*`.

```bash
branch=$(git remote show origin | sed -n 's/.*HEAD branch: //p')
git fetch origin --prune --no-tags \
  "+refs/heads/${branch}:refs/remotes/origin/${branch}" \
  "+refs/tags/*:refs/mirror/origin/tags/*"
git push <remote> "refs/remotes/origin/${branch}:refs/heads/${branch}"
git push <remote> "refs/mirror/origin/tags/*:refs/tags/*"
```

Source tags land in `refs/mirror/origin/tags/`, and only that namespace is pushed. `--prune`
drops a tag from the namespace when the source deletes it. `--no-tags` keeps the fetch from
writing `refs/tags/*`, so a local-only tag stays local and is not published. The leading `+`
replaces a tag in the namespace when upstream moves it, such as `v7`. Brace `${branch}`: in
zsh, `$branch:refs` is a modifier and corrupts the refspec. If the source has no tags, the
tag push matches nothing and exits with an error; skip it.

### 6. Handle rejected tags

A tag push is rejected when upstream moved a mutable tag (like `v7`) after the mirror last
copied it. Force-pushing overwrites the mirror's copy, so list the rejected tags and ask
before forcing them. Then force-push each one from the same mirror namespace, not from
`refs/tags/`:

```bash
git push <remote> "refs/mirror/origin/tags/<tag>:refs/tags/<tag>" --force
```

### 7. Let other repos use the Action (Actions only)

Skip this step for repos that are not Actions, and for public mirrors. Workflows in other repos
cannot use an Action from a private or internal repo until its Actions access setting allows
them, so changing `uses:` to the mirror still fails after both pushes succeed.

Ask which repos will reference the mirror. A public repo cannot use a private or internal Action
at all. If any consumer is public, stop and ask the user how to resolve the mismatch; do not
widen the mirror's visibility on your own.

Otherwise pick the narrowest access level that covers every consumer:

| Consumers | Access level |
| --------- | ------------ |
| Repos owned by the same user account | `user` |
| Repos in the same org | `organization` |

Set the level the user approved in step 2:

```bash
gh api -X PUT repos/<owner>/<name>/actions/permissions/access -f access_level=<level>
```

This API covers private repos only. For an `internal` mirror used by repos in other orgs of the
enterprise, choose the enterprise option under Settings → Actions → General → Access instead.

## Updating an existing mirror

From the clone, find the remote that points at the target with `git remote -v`, and look up the
source's default branch rather than assuming `main`:

```bash
branch=$(git remote show origin | sed -n 's/.*HEAD branch: //p')
```

Fetch that branch and every source tag into the same isolated namespace as step 5. `--prune`
drops a tag from the namespace when the source deletes it, and the leading `+` replaces a tag
there when upstream moves it, such as `v7`. Local tags under `refs/tags/` are left alone:

```bash
git fetch origin --prune --no-tags \
  "+refs/heads/${branch}:refs/remotes/origin/${branch}" \
  "+refs/tags/*:refs/mirror/origin/tags/*"
```

Confirm as in step 2 before pushing anything, and stop on anything but yes. Then push the
fetched upstream ref straight to the matching target branch, and push only the source tags,
so the result does not depend on which branch the clone has checked out or which local tags
it carries:

```bash
git push <remote> "refs/remotes/origin/${branch}:refs/heads/${branch}"
git push <remote> "refs/mirror/origin/tags/*:refs/tags/*"
```

If the source has no tags, skip the tag push. Handle rejected tags as in step 6, including
the confirmation.
