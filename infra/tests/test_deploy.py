from __future__ import annotations

from aws_cdk.assertions import Match

from config import GITHUB_REPOSITORY
from stacks.deploy import DeployStack
from tests.support import template


def test_role_trusts_only_this_repository_in_the_production_environment() -> None:
    template(DeployStack).has_resource_properties(
        "AWS::IAM::Role",
        {
            "AssumeRolePolicyDocument": {
                "Statement": [
                    Match.object_like(
                        {
                            "Action": "sts:AssumeRoleWithWebIdentity",
                            "Condition": {
                                "StringEquals": {
                                    # Guards against the audience check being dropped,
                                    # which would trust any token GitHub mints.
                                    "token.actions.githubusercontent.com:aud": (
                                        "sts.amazonaws.com"
                                    ),
                                    "token.actions.githubusercontent.com:sub": Match.array_with(
                                        [f"repo:{GITHUB_REPOSITORY}:environment:production"]
                                    ),
                                }
                            },
                        }
                    )
                ],
            }
        },
    )


def test_role_can_do_nothing_but_assume_the_bootstrap_roles() -> None:
    # Guards the blast radius. Anything else the pipeline needs is done through the
    # bootstrap roles, so a second statement here is a widening worth a conversation.
    policies = template(DeployStack).find_resources("AWS::IAM::Policy")
    (policy,) = policies.values()
    (statement,) = policy["Properties"]["PolicyDocument"]["Statement"]
    assert statement["Action"] == "sts:AssumeRole"
    assert "cdk-hnb659fds-*" in str(statement["Resource"])


def test_oidc_provider_is_not_created_here() -> None:
    # One per account, shared by every repository that deploys into it. Created by
    # `make github-oidc-provider`, never by a stack whose `cdk destroy` would take it.
    template(DeployStack).resource_count_is("AWS::IAM::OIDCProvider", 0)
    template(DeployStack).resource_count_is("Custom::AWSCDKOpenIdConnectProvider", 0)
