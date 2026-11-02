---
name: ess-shell-flags-literal
description: >-
  Write command-line flags out literally in every shell command; never pack
  several flags or arguments into one shell variable. Use when running or
  writing shell commands in zsh, especially repeated gh, aws, or pulumi calls
  that share the same flags, or when a command fails with an unknown flag or a
  bad repo name.
compatibility: >-
  Written for zsh, which does not word-split unquoted variables. The rule also
  avoids quoting bugs in bash.
---

# Write Flags Out Literally

The shell is **zsh**. Unlike bash, zsh does not word-split an unquoted `$VAR`, so a
variable holding several flags reaches the command as **one** argument. The command
then fails locally (unknown flag, bad repo name) before it ever reaches GitHub, AWS,
or Pulumi.

Every flag and its value goes in the command itself, every time, including the
fifth `gh` call in a row against the same repo.

```bash
# Bad: gh receives the single argument "--repo my-org/my-repo --json body"
GH="--repo my-org/my-repo --json body"
gh pr view 123 $GH

# Bad: same failure for any CLI
AWS_ARGS="--profile my-profile --region us-east-1"
aws ssm get-parameter --name /x $AWS_ARGS

# Good
gh pr view 123 --repo my-org/my-repo --json body
aws ssm get-parameter --name /x --profile my-profile --region us-east-1
```

## Rules

- Do not store flags, flag/value pairs, or argument lists in a string variable.
- Do not work around it with `${=VAR}`, `eval`, or `$(echo $VAR)`. Write the flags out.
- A variable may hold a **single value** used as one argument, quoted:
 `gh pr view "$PR" --repo my-org/my-repo`.
- If a long argument list genuinely must be reused within one script file, use an
 array: `args=(--repo my-org/my-repo --json body); gh pr view 123 "${args[@]}"`.
 Never do this for one-off agent shell calls.
