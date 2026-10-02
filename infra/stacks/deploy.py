"""The role GitHub Actions assumes to deploy this repository.

One stack per environment, holding one IAM role and nothing else. It is deployed by
hand, once (`make deploy-github-role`), and never by the pipeline it enables: a pipeline
cannot create the credentials it runs with, and should not be able to rewrite its own
trust policy.

**No long-lived access keys anywhere.** GitHub's OIDC provider mints a short-lived token
for each job, the role trusts that token, and the repository holds no secret that could
leak or need rotating.

By default the trust is narrowed to a GitHub *environment*:

    repo:<owner>/<repo>:environment:production

so the role cannot be assumed from a pull request, a fork, or a branch the environment
does not admit. Which branches it admits is set on the environment in GitHub, so
tightening it needs no deploy here, and the environment can require a reviewer.

GitHub offers environments to private repositories only on a paid plan, so
`DEPLOY_TRUST = "branch"` in config.py trusts a branch instead:

    repo:<owner>/<repo>:ref:refs/heads/main

That still keeps out pull requests, forks and other branches. What it gives up is the
scoping to one job: any job on `main` that may mint an OIDC token can assume the role,
which is why tests/test_deploy.py allows `id-token: write` in the deploy workflow alone.

The role's only permission is to assume the CDK bootstrap roles. `cdk deploy` does every
privileged thing — CloudFormation, the asset bucket — through those, so this role's blast
radius is exactly "can deploy CDK stacks in this account", and widening it is a
deliberate act rather than drift.

The OIDC **provider** is not created here: see `_github_oidc_provider`.
"""

from __future__ import annotations

from typing import Any

import aws_cdk as cdk
from aws_cdk import aws_iam as iam
from constructs import Construct

from config import (
    DEPLOY_TRUST,
    GITHUB_REPOSITORY,
    GITHUB_REPOSITORY_IMMUTABLE,
    PROJECT,
    DeployTrust,
)
from stacks.base import BaseStack

GITHUB_OIDC_ISSUER = "token.actions.githubusercontent.com"
GITHUB_OIDC_AUDIENCE = "sts.amazonaws.com"

# `cdk bootstrap`'s default qualifier. Change it only if the account was bootstrapped
# with `--qualifier`.
BOOTSTRAP_QUALIFIER = "hnb659fds"

# The branch deploy.yaml runs on, and the one a branch-trusting role admits.
DEPLOY_BRANCH = "main"


def trusted_subjects(environment_name: str, trust: DeployTrust) -> list[str]:
    """Every spelling of "this repository, deploying into this environment".

    Two spellings of one identity, not two identities. GitHub decides which it sends and
    is migrating from the first to the second; IAM matches a list if any element
    matches, so listing both admits nothing a single string would not.
    """
    repositories = [GITHUB_REPOSITORY]
    if GITHUB_REPOSITORY_IMMUTABLE:
        repositories.append(GITHUB_REPOSITORY_IMMUTABLE)
    if trust == "environment":
        context = f"environment:{environment_name}"
    else:
        context = f"ref:refs/heads/{DEPLOY_BRANCH}"
    return [f"repo:{repo}:{context}" for repo in repositories]


class DeployStack(BaseStack):
    """The GitHub Actions deployment role for one environment."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs: Any) -> None:
        super().__init__(
            scope,
            construct_id,
            description="The IAM role GitHub Actions assumes to deploy this repository",
            **kwargs,
        )
        environment_name = self.target.name
        subjects = trusted_subjects(environment_name, DEPLOY_TRUST)

        role = iam.Role(
            self,
            "GitHubActionsRole",
            role_name=f"{PROJECT}-github-deploy-{environment_name}",
            description=f"Assumed by GitHub Actions in {GITHUB_REPOSITORY} to deploy",
            assumed_by=iam.WebIdentityPrincipal(
                self._github_oidc_provider(),
                {
                    "StringEquals": {
                        # Both conditions are load-bearing. Without the audience the
                        # role trusts any token GitHub ever mints; without the subject,
                        # every repository on GitHub.
                        f"{GITHUB_OIDC_ISSUER}:aud": GITHUB_OIDC_AUDIENCE,
                        f"{GITHUB_OIDC_ISSUER}:sub": subjects,
                    }
                },
            ),
        )

        role.add_to_policy(
            iam.PolicyStatement(
                sid="AssumeCdkBootstrapRoles",
                actions=["sts:AssumeRole"],
                # The four roles `cdk bootstrap` created: deploy, file publishing,
                # image publishing and lookup. Scoped to this account and region, so
                # the wildcard cannot reach a bootstrap role anywhere else.
                resources=[
                    f"arn:aws:iam::{self.account}:role/"
                    f"cdk-{BOOTSTRAP_QUALIFIER}-*-{self.account}-{self.region}"
                ],
            )
        )

        cdk.CfnOutput(
            self,
            "RoleArn",
            value=role.role_arn,
            description="Set as the DEPLOY_ROLE_ARN repository variable in GitHub",
        )
        cdk.CfnOutput(
            self,
            "TrustedSubjects",
            value=" | ".join(subjects),
            description="The OIDC subjects this role accepts",
        )

    def _github_oidc_provider(self) -> str:
        """The ARN of the account's GitHub OIDC provider, which is not created here.

        IAM allows exactly one provider per issuer URL per account, and every
        repository that ever deploys into this account shares the issuer. So the
        provider is account-wide whether anyone decides that or not: owned by this
        stack, a `cdk destroy` here would break every other repository's deploys, and
        the next repository to try creating its own would get `EntityAlreadyExists`.
        `make github-oidc-provider` creates it once, idempotently.

        The ARN is fully determined by the account and the issuer, so it is built
        rather than looked up, and `cdk synth` still needs no credentials.
        """
        return f"arn:aws:iam::{self.account}:oidc-provider/{GITHUB_OIDC_ISSUER}"
