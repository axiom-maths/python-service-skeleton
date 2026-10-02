"""Where stacks deploy, what they are called, and who may deploy them.

Every value a new project has to change lives in this file. `scripts/rename.py` at the
repo root rewrites the names; the account id and the alert email are filled in by hand
once the AWS account exists.

All of it is written down rather than read from the environment. Half of these values
are a trust policy or a deployment target, and a value taken from ambient credentials
would make what gets deployed — and where — depend on whose laptop ran the command.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import aws_cdk as cdk

# The project's name. It prefixes every stack and parameter, and is the `Project` cost
# allocation tag, so it should be the repository name: a later product rename must not
# split cost history across two values. CloudFormation cannot rename a stack, so choose
# it before the first deploy.
PROJECT = "python-service-skeleton"

# The GitHub repository whose workflows may deploy. Half of the deploy role's trust
# policy — see stacks/deploy.py.
GITHUB_REPOSITORY = "axiom-maths/python-service-skeleton"

# The same repository as GitHub now spells it inside an OIDC token, with numeric ids:
# `<owner>@<owner-id>/<repo>@<repo-id>`. GitHub is migrating every repository to this
# form and newer repositories already send it. Fill it in from
#
#     gh api repos/<owner>/<repo>/actions/oidc/customization/sub
#
# whose `sub_claim_prefix` is `repo:` followed by exactly this value. Left as None, the
# role trusts only the legacy spelling, and a repository sending the new one is refused
# with an error that names neither.
GITHUB_REPOSITORY_IMMUTABLE: str | None = None

# What the deploy role trusts besides the repository: a GitHub environment, or a branch.
#
# - "environment": a job deploying into the `production` GitHub environment. Which
#   branches may deploy, and any required reviewers, are set on the environment in
#   GitHub. Private repositories get environments only on a paid GitHub plan.
# - "branch": any job running on `main`. For a private repository on GitHub Free, which
#   has no environments. There is no branch protection on Free either, so anyone with
#   write access can push to `main` and so deploy. Every Environment's role trusts that
#   same subject, so it suits a Project with one Environment.
#
# deploy.yaml has to agree: its deploy job names `environment: production` for the
# first and must not for the second, or the token's subject matches nothing.
# tests/test_deploy.py fails until the two agree. See ADR-0013.
DeployTrust = Literal["environment", "branch"]
DEPLOY_TRUST: DeployTrust = "environment"

# The AWS account and region. The placeholder account synthesises (CI and the tests
# need nothing more), but any deploy refuses it: the CDK checks the account against the
# credentials in use, so a stack cannot land in the wrong account by accident.
ACCOUNT = "000000000000"
REGION = "eu-west-2"

# Where the budget and the alarms send their Alerts. Each address receives a confirmation
# email from AWS after the first deploy, and gets nothing until the link is clicked.
ALERT_EMAIL = "alerts@example.com"

# Monthly spend in USD past which the budget emails. Raise it as real usage grows.
MONTHLY_BUDGET_USD = 25


@dataclass(frozen=True)
class Target:
    """An account and region, plus the `Environment` tag stacks there carry."""

    name: str
    account: str
    region: str
    environment_tag: str

    @property
    def env(self) -> cdk.Environment:
        return cdk.Environment(account=self.account, region=self.region)

    def stack_name(self, stack: str) -> str:
        """`<project>-<stack>-<target>`, e.g. `python-service-skeleton-service-production`.

        The target suffix stays even with one target, because adding a second later
        must not mean renaming the first — and CloudFormation cannot rename a stack.
        """
        return f"{PROJECT}-{stack}-{self.name}"

    def parameter_name(self, name: str) -> str:
        """`/<project>/<target>/<name>`: where one stack publishes a value for another."""
        return f"/{PROJECT}/{self.name}/{name}"


# What all of the Project's Environments share: its budget and its alert topic. Not an
# Environment itself, since no Service runs here. Tagged `shared` rather than
# `production` because these back every Environment at once, and booking them to one
# would misstate where its money goes.
SHARED = Target(name="shared", account=ACCOUNT, region=REGION, environment_tag="shared")

# The production Environment, in the same account. A staging Environment, if one is
# ever wanted, is another Target — ideally in another account.
PRODUCTION = Target(name="production", account=ACCOUNT, region=REGION, environment_tag="production")

# Where the alerts stack publishes the alert topic's ARN. A name both sides agree on,
# rather than a cross-stack reference — see "The seam between stacks" in docs/infra.md.
ALERTS_TOPIC_PARAMETER = SHARED.parameter_name("alerts-topic-arn")
