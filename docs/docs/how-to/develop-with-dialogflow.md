# Develop with Dialogflow

## Problem

[Google Dialogflow](https://cloud.google.com/dialogflow/docs/) intents, entities, etc. are developed using the [Dialogflow console](https://dialogflow.cloud.google.com). This console makes it easy to add training phrases and test. But it doesn't provide a way to move code from a sandbox to development, then to staging and production environments.

**Solution:** Export Dialogflow agents from the console. Agents are exported as a zipped file of JSON files.

However, exported Dialogflow agents may contain personally identifiable information (PII) used to train them. They certainly contain object IDs that [shouldn't be committed to a repository](https://12factor.net/config).

**Solution:** Use [DVC](https://dvc.org/) - "data version control". It's like git for data. Rather than commit the files themselves, you store them elsewhere (e.g., local file system, cloud storage) and commit only their hashes to git.

## Solution

- Export Dialogflow agents from the Dialagflow console.
- Commit them to the repository with DVC.

## Install

Run the following commands to:

- Install `dvc`.
- Initialize it within this monorepo.
- Configure local file storage.
- Track the ignored data files.

```sh
brew install dvc
npm run dvc:setup
```

**Note:** DVC will maintain `data/agents/.gitignore` as you add files to the repo with `dvc add`.

## Track a Dialogflow agent

Download the agent from the Google project denoted by the environment variable `INTENT_API_ID`.

```sh
npm run agent:download
```

Save the agent.

```sh
npm run agent:save
```

Stage and commit the agent.

```sh
export AGENT_BASE_NAME=conversational-agent

dvc add data/agents/${AGENT_BASE_NAME}.zip
git add data/agents/${AGENT_BASE_NAME}.zip.dvc
npm run git:commit
```

## Download an agent from another project

Download the agent from the Google project denoted by the environment variable `INTENT_EXTERNAL_API_ID`.

```sh
npm run agent:download:external
```

Push this agent to the remote Dialogflow console.

```sh
npm run agent:release
```

You can now develop the corresponding code using this "external" agent. (Remember, your original project agent is versioned with DVC and git. You can revert at any time.)

If you're satisfied with the results, add this agent to your project.

```sh
export AGENT_BASE_NAME=conversational-agent

dvc add data/agents/${AGENT_BASE_NAME}.zip
git add data/agents/${AGENT_BASE_NAME}.zip.dvc
npm run git:commit
```

### Figure

_Dialogflow development workflow_

![Dialogflow development workflow](/develop-with-dialogflow/development-sequence-diagram.png)
