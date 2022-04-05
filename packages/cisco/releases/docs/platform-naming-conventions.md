# Platform naming conventions

> Note: OpenShift project _names_ are equivalent to Google Cloud project _IDs_.

## [Google Cloud Container Registry](https://cloud.google.com/container-registry/)

### Parts

- Hostname
  - Location: southamerica-east1
  - Base: docker.pkg.dev
- Project ID: my-project
- Org (Repository, Team): team1, e.g., gve
- Image name: my-bot

### Examples

- southamerica-east1-docker.pkg.dev/my-project/team1/my-bot
- australia-southeast1-docker.pkg.dev/my-project/team2/my-bot

## containers.cisco.com, powered by OpenShift

### Vocabulary

- Org (Organization)
  - Example: https://containers.cisco.com/organization/gve
- Repository = Org + / + Image name
  - Example: https://containers.cisco.com/repository/gve/my-bot

### Parts

- Hostname
  - Base: containers.cisco.com
- Project ID: _N/A_
- Org (Repository, Team): team1, e.g., gve
- Image name: my-bot
