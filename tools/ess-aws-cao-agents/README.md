# CAO Agent Profiles

Agent profiles for [CLI Agent Orchestrator (CAO)](https://github.com/awslabs/cli-agent-orchestrator), an open-source multi-agent orchestrator from AWS that coordinates CLI coding agents in tmux sessions.

These profiles use **Claude Code** as the developer and **Codex CLI** as the code reviewer. A built-in supervisor coordinates them in a review loop until the reviewer approves.

## Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code/getting-started) installed and authenticated (AWS Bedrock)
- [GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/cli-getting-started) installed and authenticated (required for copilot-reviewer)
- [uv](https://docs.astral.sh/uv/) installed
- macOS 12+, Ubuntu 20.04+, or Windows 11 via WSL2

## Setup

### 1. Install Codex CLI

```bash
brew install --cask codex
```

Or with npm:

```bash
npm install -g @openai/codex
```

### 2. Install GitHub Copilot CLI

Required for the `copilot-reviewer` profile.

```bash
brew install copilot-cli          # macOS/Linux (Homebrew)
npm install -g @github/copilot    # Cross-platform (Node.js 22+)
```

Authenticate:

```bash
copilot auth login
```

See the [CLI getting started guide](https://docs.github.com/en/copilot/how-tos/copilot-cli/cli-getting-started).

### 3. Configure Codex for Azure OpenAI

Create `~/.codex/config.toml`:

```toml
model = "gpt-5.4"
model_provider = "azure-openai"
model_reasoning_effort = "xhigh"

[model_providers.azure-openai]
name = "Azure OpenAI"
base_url = "https://<YOUR-ACCOUNT-NAME>.openai.azure.com/openai/v1"
env_key = "AZURE_OPENAI_API_KEY"

# Increase MCP timeout for CAO handoffs (default is too short for large reviews)
[mcp_servers.cao-mcp-server]
tool_timeout_sec = 1200.0
```

Add to your `~/.zshrc`:

```bash
# Codex CLI - Azure OpenAI
export AZURE_OPENAI_API_KEY="<your-api-key>"
```

Replace `<YOUR-ACCOUNT-NAME>` with your Azure OpenAI resource name and
`<your-api-key>` with one of its keys, both shown under **Keys and Endpoint** in
the Azure portal. See
[Create and deploy an Azure OpenAI resource](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/create-resource).

### 4. Install tmux

```bash
brew install tmux
```

Verify version 3.3+:

```bash
tmux -V
```

### 5. Install CAO

```bash
uv tool install git+https://github.com/awslabs/cli-agent-orchestrator.git@0344496ef938 --upgrade
```

> **Why pin?** Pinning to a commit SHA ensures everyone using these profiles
> gets the same version. Tracking `@main` can break unexpectedly when upstream changes.
> To upgrade, get the latest SHA from
> [the repo](https://github.com/awslabs/cli-agent-orchestrator/commits/main),
> update the SHA here and in the agent profiles, then reinstall.

### 6. Install agent profiles

```bash
# Built-in supervisor (orchestrates developer + reviewer)
cao install code_supervisor

# Custom profiles from this repo
cao install tools/ess-aws-cao-agents/agents/developer.md
cao install tools/ess-aws-cao-agents/agents/copilot-reviewer.md
cao install tools/ess-aws-cao-agents/agents/codex-reviewer.md
```

## Usage

### Start the review loop

```bash
# Terminal 1: Start the CAO server
cao-server

# Terminal 2: Launch the supervisor (fully autonomous)
cao launch --agents code_supervisor --provider claude_code --yolo
```

> **`--yolo`** skips all confirmation prompts so agents run fully autonomous.
> Only use in trusted repos -- agents get unrestricted shell access.

Tell the supervisor which reviewer to use in your prompt:

```
Review and fix changes on this branch. Use codex-reviewer for reviews and developer for fixes.
```

> **Note:** The `copilot-reviewer` (GitHub Copilot CLI) may fail with a 500
> on cross-provider handoffs. Use `codex-reviewer` for reliable autonomous runs.
> The `copilot-reviewer` is available for manual/interactive sessions.

The supervisor will:

1. Assign coding tasks to the **developer** (Claude Code)
2. Send code for review to the specified **reviewer**
3. Loop between them until the reviewer approves

By default, reviewers diff against `origin/main`. To change the scope:

```
Review changes from abc1234. Use copilot-reviewer for reviews and developer for fixes.
Review the last 3 commits. Use codex-reviewer for reviews and developer for fixes.
```

### Interact with sessions

```bash
# List all tmux sessions
tmux list-sessions

# Attach to watch a specific agent work
tmux attach -t <session-name>

# Detach from a session
# Ctrl+b, then d

# Shutdown everything
cao shutdown --all
```

## Agent Profiles

| Profile            | Provider       | Role       | Description                                        |
| ------------------ | -------------- | ---------- | -------------------------------------------------- |
| `code_supervisor`  | (built-in)     | supervisor | Coordinates developer and reviewer in a loop       |
| `developer`        | Claude Code    | developer  | Writes and fixes code                              |
| `copilot-reviewer` | GitHub Copilot | reviewer   | Exhaustive review using Copilot CLI (Azure-backed) |
| `codex-reviewer`   | Codex          | reviewer   | Exhaustive review using Codex CLI                  |

## Managing Installed Profiles

CAO stores installed profiles in `~/.aws/cli-agent-orchestrator/agent-context/`.
Source copies are also kept in `~/.aws/cli-agent-orchestrator/agent-store/`.

```bash
# List installed agents
ls ~/.aws/cli-agent-orchestrator/agent-context/
ls ~/.aws/cli-agent-orchestrator/agent-store/

# Remove an agent (delete from both locations)
rm ~/.aws/cli-agent-orchestrator/agent-context/<agent-name>.md
rm ~/.aws/cli-agent-orchestrator/agent-store/<agent-name>.md
```

## References

- [CAO GitHub](https://github.com/awslabs/cli-agent-orchestrator)
- [CAO agent profile docs](https://github.com/awslabs/cli-agent-orchestrator/blob/main/docs/agent-profile.md)
- [CAO Codex provider](https://github.com/awslabs/cli-agent-orchestrator/blob/main/docs/codex-cli.md)
- [CAO Claude Code provider](https://github.com/awslabs/cli-agent-orchestrator/blob/main/docs/claude-code.md)
- [Codex CLI](https://github.com/openai/codex)
- [Azure Responses API](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/responses)
