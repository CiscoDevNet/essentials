"""Locust entrypoint — default scenario only.

Deployment layout: the cluster runner syncs this directory to EC2 as flat files
under the configured install dir (``locustfile.py``, ``locust_runtime.py``, …)
with ``PYTHONPATH`` set there. Imports therefore use bare module names on workers.

In the monorepo the same sources live under ``ess_load_test.locust.*``.
Each file uses ``try/except ImportError`` so pylint, tests, and EC2 all resolve
imports without inline ``pylint: disable=import-error`` suppressions.
"""

import os

from locust import events

try:
    from locust_runtime import normalize_scenario
except ImportError:
    from ess_load_test.locust.runtime import normalize_scenario

try:
    from scenario_default import LoadTestUser
except ImportError:
    from ess_load_test.locust.scenario_default import LoadTestUser

_SCENARIO = normalize_scenario(os.environ.get("LOAD_TEST_SCENARIO"))

_LOCUST_RUN_PROFILES = ("smoke", "default-run")


@events.init.add_listener
def on_locust_init(environment, **_kwargs) -> None:
    """Suggest run labels in the Locust web UI Profile field."""
    if environment.web_ui is None:
        return

    environment.web_ui.template_args["all_profiles"] = list(_LOCUST_RUN_PROFILES)


# Locust discovers HttpUser subclasses imported here; the tuple references
# them so pylint does not report the imports as unused (F401).
_LOCUST_USER_CLASSES = (LoadTestUser,)
