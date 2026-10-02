# Deploy role per repository, trusting a GitHub environment

There is one deploy role per repository and Environment. It trusts
`repo:<owner>/<repo>:environment:production`, checks `aud` as well as `sub`, and may only
assume the CDK bootstrap roles. A trust policy names one repository, so a role cannot be
shared without widening it. Trusting a GitHub environment rather than a branch lets the
environment's branch rules and reviewers decide who deploys, and keeps pull requests and
forks out. Limiting it to the bootstrap roles means the role can do no more than
`cdk deploy`.

A private repository on GitHub Free has no environments, and trusts a branch instead:
see [ADR-0013](0013-a-branch-trusting-deploy-role-for-github-free.md).
