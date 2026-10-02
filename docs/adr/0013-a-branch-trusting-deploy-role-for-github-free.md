# A branch-trusting deploy role, for GitHub Free

`DEPLOY_TRUST` in `infra/config.py` decides what the deploy role trusts besides the
repository. `"environment"`, the default, keeps
[ADR-0004](0004-deploy-role-per-repository-trusting-a-github-environment.md): the
`production` GitHub environment. `"branch"` trusts `repo:<owner>/<repo>:ref:refs/heads/main`.
GitHub offers environments to private repositories only on a paid plan, so without
the setting a private Project on GitHub Free could not turn its pipeline on at all.

On Free, a branch subject loses almost nothing. An environment's branch rule is only as
strong as the rules on who can push to that branch, and a private repository on Free has
no branch protection, so either way anyone with write access can deploy. Required
reviewers are not available there either. A pull request, a fork and every other branch
are still refused, because the token's subject carries the ref.

## Considered Options

- *Deploy by hand,* and leave the pipeline off. The same people can deploy as under a
  branch subject, by a path that skips CI and depends on whose laptop ran it.
- *Make the repository public,* which gives it environments on any plan. Not every
  Project's account id and configuration should be public.
- *Read the setting in the workflow,* rather than editing `deploy.yaml` by hand. An
  `environment:` expression that evaluates to an empty string would have to mean "no
  environment", which nothing here could test before the first merge to `main`.

## Consequences

- The workflow has to agree with the setting: naming an environment replaces the ref in
  the token's subject. A test reads `deploy.yaml` and fails while they disagree.
- Under a branch subject, any job on `main` that can mint an OIDC token can assume the
  role, not just the one that names the environment. A test holds `id-token: write` to
  the deploy job, and `pull_request_target`, which runs with `main` as its ref, must
  never be given it.
- Every Environment's role trusts the same subject, so a branch subject cannot keep a
  staging deploy away from production's role. It suits a Project with one Environment.
