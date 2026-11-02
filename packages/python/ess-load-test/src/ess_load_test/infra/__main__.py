"""Pulumi entrypoint for the generic Locust load test EC2 cluster."""

from ess_load_test.infra.stack import deploy_cluster

deploy_cluster()
