# Releases

Build [Docker](https://www.docker.com/) images and deploy containers to [Google Cloud](https://cloud.google.com/) or [OpenShift](https://www.openshift.com/).

## Installation

Install with [npm](https://www.npmjs.com/).

```bash
npm i @gve/releases
```

## Usage

```js
const { OpenShiftRelease } = require("@gve/releases");

// Create the release.
const RELEASES_PROJECT_NAME =
  "OpenShift project name or Google Cloud project ID";
const release = new OpenShiftRelease({ projectName: RELEASES_PROJECT_NAME });

// Build its Docker image.
release.build();

// Intermediate step: Use the Docker CLI to upload the image to its image repository.

// Build a deployment and release it to OpenShift.
release.buildDeployment();
release.release();
```

- Creates a scoped, named, and tagged Docker image
- Creates its deployment files for release
- Pushes the deployment files to the run platform, e.g, OpenShift

## License

[Apache 2.0](https://choosealicense.com/licenses/apache-2.0/)
