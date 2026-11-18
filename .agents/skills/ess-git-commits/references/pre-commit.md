# Install the strip-cursor-coauthor hook

The hook runs [`scripts/strip-cursor-coauthor.sh`](../scripts/strip-cursor-coauthor.sh)
at the commit-msg stage and removes the `Co-authored-by: Cursor` trailer. The script is
stand-alone bash; it needs only `grep` and `mktemp`.

1. Install this skill into the repo, for example with APM, and commit the installed copy.
   The hook runs that copy, so a fresh clone without it has no hook to run.
2. Add the hook to `.pre-commit-config.yaml`:

   ```yaml
   repos:
     - repo: local
       hooks:
         - id: strip-cursor-coauthor
           name: strip Cursor co-author trailer
           entry: bash .agents/skills/ess-git-commits/scripts/strip-cursor-coauthor.sh
           language: system
           stages: [commit-msg]
           pass_filenames: true
   ```

   `entry` runs the script through `bash`, so the hook works even if the installer drops
   the executable bit. Adjust the path if your installer writes skills somewhere other
   than `.agents/skills/`.

3. Make `pre-commit install` set up the commit-msg stage. Without this line it installs
   only the pre-commit stage, and the hook never runs:

   ```yaml
   default_install_hook_types: [pre-commit, commit-msg]
   ```

4. Install the hooks once per checkout, then confirm on a test commit:

   ```bash
   pre-commit install
   git log -1 --format=full
   ```

If commit-message checks such as commitizen also run at commit-msg, list this hook first,
so a rejected message is never the trailer's fault.
