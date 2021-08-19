import os


def get_project_id():
    return (
        os.getenv("GOOGLE_CLOUD_PROJECT")
        or os.getenv("GCLOUD_PROJECT")
        or os.getenv("gcloud_project")
        or os.getenv("google_cloud_project")
    )


GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
GOOGLE_CLOUD_PROJECT = get_project_id()
GVE_GOOGLE_EMAIL = os.getenv("GVE_GOOGLE_EMAIL")
GVE_GOOGLE_KEY = os.getenv("GVE_GOOGLE_KEY")
