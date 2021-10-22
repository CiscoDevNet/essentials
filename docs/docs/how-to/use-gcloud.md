---
title: "gcloud CLI"
---

# How to use the gcloud CLI

Manage your [Google Cloud](https://cloud.google.com/) projects and applications with the `gcloud` command line tool.

## 📁 Projects

List projects.

```bash
gcloud projects list
```

Set active project.

```bash
gcloud config set project ${GOOGLE_CLOUD_PROJECT_ID}
```

Get active project.

```bash
gcloud config get-value project
```

## 🤖 Service accounts

Use [service accounts](https://cloud.google.com/iam/docs/service-accounts) to access APIs like [Dialogflow](https://cloud.google.com/dialogflow/docs/).

List service accounts.

```bash
gcloud iam service-accounts list
```

View the properties of a particular service account.Service account emails look like this: `${SERVICE_ACCOUNT_NAME}@${GOOGLE_CLOUD_PROJECT_ID}.iam.gserviceaccount.com`

```bash
gcloud iam service-accounts describe ${SERVICE_ACCOUNT_EMAIL}
```

List keys of a service account.

```bash
gcloud iam service-accounts keys list --iam-account=${SERVICE_ACCOUNT_EMAIL}
```
