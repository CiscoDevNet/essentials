---
name: ess-git-commits
description: >-
  Commit and open pull requests as an agent without agent attribution: no
  Co-authored-by trailer, no "Made with Cursor" footer. Commit with plain git
  commit and let a commit-msg hook strip the trailer Cursor injects. Use when
  committing, amending, creating or editing a pull request, or when a commit
  shows a "Co-authored-by: Cursor" trailer.
compatibility: >-
  Targets Cursor agents, which add the trailer. Requires git; the hook needs
  pre-commit with the commit-msg stage installed.
---

# Git Commits

Commit messages and pull requests contain only what the user asked for. Never add
`Co-authored-by:` trailers or any other agent attribution.

Cursor appends a `Co-authored-by: Cursor` trailer to every agent `git commit`, whatever the
settings or rules say. The `strip-cursor-coauthor` commit-msg hook, bundled as
[scripts/strip-cursor-coauthor.sh](scripts/strip-cursor-coauthor.sh), removes it before
the commit is created, so commit normally and let the hooks run. To add the hook to a
repo, follow [references/pre-commit.md](references/pre-commit.md).

The commands below call `pre-commit` directly. If the repo runs it through a tool
runner, such as `uv run pre-commit`, use that form instead.

## Committing

1. Once per checkout, make sure the commit-msg hook is installed. A plain install covers
   every stage listed in `default_install_hook_types`:

   ```bash
   test -x "$(git rev-parse --git-path hooks)/commit-msg" || pre-commit install
   ```

2. Commit with `git commit`. Never pass `--no-verify`: it skips the hook that removes the
   trailer, along with the message checks.
3. Verify with `git log -1 --format=full`. If the trailer is still there, the hook did not
   run: install it (step 1), then `git commit --amend --no-edit` while the commit is unpushed.

## Fallback: no hooks

If installing the hooks is not an option, build the commit with `git commit-tree`, which
Cursor leaves alone. It skips every hook too, so write the message to a file and run them
yourself first:

```bash
pre-commit run --files $(git diff --cached --name-only)
cat > /tmp/commit-msg <<'EOF'
<type>(<scope>): <subject>

<body>
EOF
pre-commit run --hook-stage commit-msg --commit-msg-filename /tmp/commit-msg
old=$(git rev-parse HEAD)
new=$(git commit-tree "$(git write-tree)" -p "$old" < /tmp/commit-msg)
git update-ref "refs/heads/$(git branch --show-current)" "$new" "$old"
```

Passing the old tip makes `update-ref` fail if the branch moved in the meantime.

## Pull requests

- Never append `Made with Cursor`, `Made with [Cursor](https://cursor.com)`, or similar
  attribution to PR titles or bodies.
- PR descriptions contain only **Summary** and **Test plan**, or what the user asked for.
- After `gh pr create` or `gh pr edit`, check `gh pr view <number> --json body` and remove
  any injected footer.
