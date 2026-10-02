from __future__ import annotations

import re
from pathlib import Path

from aws_cdk.assertions import Match

from config import DEPLOY_TRUST, GITHUB_REPOSITORY, PRODUCTION
from stacks.deploy import DeployStack, trusted_subjects
from tests.support import template

_WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"


def test_environment_trust_names_the_github_environment() -> None:
    assert f"repo:{GITHUB_REPOSITORY}:environment:production" in trusted_subjects(
        "production", "environment"
    )


def test_branch_trust_names_main_and_no_environment() -> None:
    subjects = trusted_subjects("production", "branch")
    assert f"repo:{GITHUB_REPOSITORY}:ref:refs/heads/main" in subjects
    assert not any("environment" in subject for subject in subjects)


def test_role_trusts_only_this_repository_as_configured() -> None:
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
                                    "token.actions.githubusercontent.com:sub": (
                                        trusted_subjects(PRODUCTION.name, DEPLOY_TRUST)
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


def test_deploy_workflow_names_the_environment_exactly_when_the_role_trusts_one() -> None:
    # The role's trust lives in config.py, the job's `environment:` in deploy.yaml, and
    # nothing else ties them together. Naming an environment puts it in the token's
    # subject, so a mismatch either way is `Not authorized to perform
    # sts:AssumeRoleWithWebIdentity` on the first merge after the pipeline is on.
    workflow = (_WORKFLOWS / "deploy.yaml").read_text()
    named = re.findall(r"^\s+environment:\s*(\S+)\s*$", workflow, re.MULTILINE)
    expected = [PRODUCTION.name] if DEPLOY_TRUST == "environment" else []
    assert named == expected, f"DEPLOY_TRUST is {DEPLOY_TRUST!r} in config.py"


def test_only_the_deploy_workflow_can_mint_an_oidc_token() -> None:
    # A branch-trusting role admits any job on `main` that can mint a token, so the
    # deploy job must be the only one. Worth holding under environment trust as well:
    # it is the difference between one way to reach AWS and one per workflow.
    grants = {
        path.name: len(re.findall(r"^\s*id-token:\s*write\b", path.read_text(), re.MULTILINE))
        for path in sorted(_WORKFLOWS.glob("*.y*ml"))
    }
    assert {name: count for name, count in grants.items() if count} == {"deploy.yaml": 1}
