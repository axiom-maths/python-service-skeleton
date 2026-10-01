"""What every stack in this repo has in common.

Subclass `BaseStack`, never `cdk.Stack`. It binds the stack to a `Target`, so where it
deploys and how it is tagged cannot be forgotten on a new stack, and it makes the
CloudFormation console say which repository the stack came from.
"""

from __future__ import annotations

from typing import Any

import aws_cdk as cdk
from constructs import Construct

from config import GITHUB_REPOSITORY, PROJECT, Target


class BaseStack(cdk.Stack):
    """A stack pinned to a `Target`, described, and tagged for cost allocation."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        target: Target,
        description: str,
        **kwargs: Any,
    ) -> None:
        # The description is required. An account soon holds stacks from more than one
        # place — `cdk bootstrap`'s own, and later another repository's — and the
        # console gives no other clue where a stack's code lives.
        super().__init__(
            scope,
            construct_id,
            env=target.env,
            description=f"{description.rstrip('.')}. Managed by {GITHUB_REPOSITORY}.",
            **kwargs,
        )
        self.target = target

        # Cost allocation. A tag only groups spend in Cost Explorer once it has been
        # activated as a cost allocation tag in Billing, which AWS allows only after
        # it has appeared on a resource — so activate these a day after the first
        # deploy, not when someone first asks what something cost.
        cdk.Tags.of(self).add("Project", PROJECT)
        cdk.Tags.of(self).add("Environment", target.environment_tag)
        cdk.Tags.of(self).add("ManagedBy", "cdk")
