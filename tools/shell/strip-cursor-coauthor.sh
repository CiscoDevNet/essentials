#!/usr/bin/env bash
# Remove the `Co-authored-by: Cursor` trailer from a commit message.
#
# Cursor appends the trailer while composing the message, before git runs any
# hook. `--no-verify` does not suppress it and `git commit --amend` re-adds it,
# so a commit-msg hook is the only place that reliably removes it without
# rewriting the commit afterwards. The IDE toggle (Cursor Settings -> Git &
# Pull Requests -> Attribution) covers the local case; this hook also covers
# contributors who have not set it and surfaces that Cloud Agents ignore it.
#
# Matches the agent's mailbox rather than its display name: a human
# contributor could be called "Cursor", but only the bot commits from this
# address. Human `Co-authored-by:` lines are left untouched.

set -euo pipefail

readonly CURSOR_TRAILER='^Co-authored-by:.*<cursoragent@cursor\.com>'

msg_file="${1:?usage: strip-cursor-coauthor.sh <commit-msg-file>}"

if ! grep -qiE "$CURSOR_TRAILER" "$msg_file"; then
    exit 0
fi

stripped="$(mktemp)"
trap 'rm -f "$stripped"' EXIT

# `|| true`: grep exits 1 when it filters out every line, which `set -e`
# would otherwise treat as a failure.
grep -viE "$CURSOR_TRAILER" "$msg_file" >"$stripped" || true

# The command substitution drops the blank line the trailer left behind.
printf '%s\n' "$(cat "$stripped")" >"$msg_file"
