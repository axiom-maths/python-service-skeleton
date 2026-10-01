#!/usr/bin/env python3
"""The CDK app: every stack this repository deploys.

    <project>-alerts-shared          the Project's budget and alert topic
    <project>-service-production     the example service
    <project>-deploy-production      the role GitHub Actions deploys with

Deploy `alerts` first: the service's alarms notify the topic it publishes. `deploy` is
on its own timeline — deployed by hand, once, and never by the pipeline.

Stacks are wired together by names and never by passing one stack's constructs to
another, so that any one of them can move to another repository unchanged. A test holds
that line: see tests/test_app.py.
"""

from __future__ import annotations

import aws_cdk as cdk

from config import PRODUCTION, SHARED
from stacks.alerts import AlertsStack
from stacks.deploy import DeployStack
from stacks.service import ServiceStack


def build(app: cdk.App) -> None:
    alerts = AlertsStack(app, SHARED.stack_name("alerts"), target=SHARED)

    service = ServiceStack(app, PRODUCTION.stack_name("service"), target=PRODUCTION)
    # Deploy order only, not a reference: the service reads the alert topic's parameter
    # at deploy time, so on a first deploy the alerts stack has to have published it.
    # Neither template mentions the other. If the alerts stack moves to another
    # repository, delete this line and nothing else changes.
    service.add_stack_dependency(alerts)

    DeployStack(app, PRODUCTION.stack_name("deploy"), target=PRODUCTION)


if __name__ == "__main__":
    app = cdk.App()
    build(app)
    app.synth()
