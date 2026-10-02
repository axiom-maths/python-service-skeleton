# Infrastructure

The AWS footprint, in CDK Python. Every value a new project changes, such as names, the
account, the region, the alert email and the budget, is in [infra/config.py](../infra/config.py).

| Stack | Holds |
| --- | --- |
| `<project>-alerts-shared` | The Project's monthly budget, and the SNS topic its alarms notify |
| `<project>-service-production` | The example Service: a scheduled Lambda, its dead-letter queue, and alarms for Failures and Missed runs |
| `<project>-deploy-production` | The IAM role GitHub Actions assumes to deploy the other two |

Two things are deliberately left out of CDK. The **GitHub OIDC provider** is shared by
the whole account, and `make github-oidc-provider` creates it
([ADR-0003](adr/0003-github-oidc-provider-created-by-a-make-target.md)).
**IAM Identity Center** is set up in the console
([aws-access.md](aws-access.md)).

## Commands

From the repo root:

```bash
make synth      # templates only; needs no AWS credentials
make diff       # what a deploy would change
make deploy     # the alerts stack, then the service
```

**`synth` makes no AWS calls.** The account and region are pinned in `config.py`, and
nothing is looked up at synth time, so CI checks every template without credentials.
When a stack needs a value from AWS, resolve it at deploy time with an SSM parameter or a
dynamic reference, never with `from_lookup`.

`diff` and `deploy` need an AWS session, and log in if it has expired. Once the pipeline
is on, a merge to `main` deploys, but the targets stay so that a failing deploy can be
debugged locally.

## The first deploy

Set up [AWS access](aws-access.md) first. Each command needs an
**administrator** session, for example `AWS_PROFILE=admin make bootstrap`.

```bash
make bootstrap    # once per account and region: the CDK's own bucket and roles
make diff         # the first time, this lists every resource being created
make deploy
```

**Then confirm the email.** AWS sends a confirmation link to `ALERT_EMAIL`, and alarms
reach nobody until it has been clicked.

**The next day, activate the cost allocation tags.** In Billing, under *Cost allocation
tags*, activate `Project`, `Environment` and `ManagedBy`. AWS lists a tag only once a
resource carries it, which takes up to a day after the first deploy. This step is not
optional: **the budget counts only spend tagged with this Project, so until `Project` is
activated it counts $0 and can never warn.** Nothing looks wrong while that lasts.

Expect the Missed-run alarm to be in alarm until the first scheduled Run. Straight after
a deploy there has been no Run in the last 26 hours. It tells nobody, because the email
subscription is not confirmed yet and an alarm notifies only when its state changes.

## The deployment pipeline

`.github/workflows/deploy.yaml` runs CI on every push to `main`, then `make deploy` if
CI passed. The deploy step is skipped until the pipeline is turned on, so a fresh copy's
`main` does not fail for want of an AWS account.

The workflow assumes `<project>-github-deploy-production` through GitHub's OIDC
provider. The role trusts only this repository deploying into the `production`
environment, and its only permission is to assume the CDK bootstrap roles
([ADR-0004](adr/0004-deploy-role-per-repository-trusting-a-github-environment.md)).
A private repository on GitHub Free has no environments, so there the role trusts
`main` instead ([ADR-0013](adr/0013-a-branch-trusting-deploy-role-for-github-free.md)).

### Turning it on

Once per repository, as an administrator:

```bash
make github-oidc-provider    # account-wide; reuses the existing provider if there is one
make deploy-github-role      # prints the role's ARN
```

Then create the `production` environment in GitHub, limit it to `main`, and give the
workflow the role:

```bash
gh api -X PUT repos/<owner>/<name>/environments/production \
  --input - <<<'{"deployment_branch_policy":{"protected_branches":false,"custom_branch_policies":true}}'
gh api -X POST repos/<owner>/<name>/environments/production/deployment-branch-policies \
  -f name=main -f type=branch
gh variable set DEPLOY_ROLE_ARN --body arn:aws:iam::<account>:role/<name>-github-deploy-production
```

The role trusts the environment, and the environment's branch rule is what stops a
`workflow_dispatch` from another branch from deploying. Required reviewers, if you want
them, also go on the environment.

**A private repository on GitHub Free** cannot have environments. Before
`make deploy-github-role`, set `DEPLOY_TRUST = "branch"` in `config.py` and delete the
`environment: production` line from `.github/workflows/deploy.yaml` (`make ci` fails
until both are done). Skip the two `environments` calls above, and set the variable as
shown. The role then trusts any job on `main`, and the token's own subject keeps out a
`workflow_dispatch` from another branch. Free has no branch protection for a private
repository either, so anyone with write access can deploy by pushing to `main`. When
the organisation moves to a paid plan, switch both back and deploy the role again.

**Check which spelling of the repository GitHub sends.** Newer repositories put numeric
ids in the OIDC subject:

```bash
gh api repos/<owner>/<name>/actions/oidc/customization/sub
```

If `sub_claim_prefix` contains `@` and a number, copy everything after `repo:` into
`GITHUB_REPOSITORY_IMMUTABLE` in `config.py` and run `make deploy-github-role` again.
The role then trusts both spellings, which name the same repository.

### When a deploy fails

- **`Not authorized to perform sts:AssumeRoleWithWebIdentity`.** The token's subject
  did not match the trust policy. The error looks the same as for a role that does not
  exist. Check, in order: the job names the environment (or, with
  `DEPLOY_TRUST = "branch"`, does not), the branch is one the role or environment
  admits, and the role trusts the spelling GitHub sends. The stack output
  `TrustedSubjects` lists what the role accepts.
- **The CDK refuses because the account does not match.** `ACCOUNT` in `config.py` is
  still the placeholder, or your credentials are for another account.
- **The budget `already exists`.** A budget of the same name was made by hand. Delete
  it, then deploy again.
- **The service stack cannot find the alert topic's parameter.** The alerts stack is
  not deployed yet. `make deploy` orders them, but `STACKS=` can skip one.
- **A stack is stuck in `UPDATE_ROLLBACK_FAILED`.** Continue the rollback from the
  CloudFormation console, then re-run the workflow with `workflow_dispatch`.

## The seam between stacks

Stacks never pass constructs to each other. A stack that owns a value publishes it as an
SSM parameter under `/<project>/<target>/<name>`, and a stack that needs it reads it by
that name. The alert topic is the example: [infra/stacks/alerts.py](../infra/stacks/alerts.py)
publishes its ARN and [infra/stacks/service.py](../infra/stacks/service.py) reads it.

A construct passed between stacks becomes a CloudFormation export, which can be neither
changed nor deleted while anything imports it. That ties the two stacks together for
good ([ADR-0002](adr/0002-stacks-share-values-by-ssm-parameter-name.md)).
[infra/tests/test_app.py](../infra/tests/test_app.py) fails on any export or import. When two stacks
must deploy in order, use `add_stack_dependency` as [infra/app.py](../infra/app.py) does. It sets the
order without changing either template.

## Splitting infrastructure out

Infrastructure that several Projects use, such as a network or a database, can move to a
repository of its own. Today there is none: the alerts stack belongs to this Project
([ADR-0012](adr/0012-each-project-owns-its-alerts.md)). Each Project keeps its
own Service stack, alerts stack and deploy role, because the Service stack packages
`src/` and the role trusts this repository by name.

1. Copy `infra/` into the new repository as its root. It is already a complete uv
   project. Bring over the CDK targets from the `Makefile`, the `infra` job from
   `ci.yaml`, this page, and the ADRs that still apply, then fix their links.
2. Delete the stacks that stay behind from the new repository. Here, delete the stacks
   that moved, and the `add_stack_dependency` between them.
3. Give the new repository its own deploy role by copying `stacks/deploy.py`.
4. Run `make diff` in the new repository. With the same stack names and logical ids, it
   should show no changes.

Parameter names do not change, so nothing that reads them notices.

## What it costs

At eu-west-2 prices, effectively nothing:

| Service | Cost |
| --- | --- |
| Lambda, EventBridge Scheduler | Within the free tier |
| SQS, SNS email, SSM standard parameters | Free at this volume |
| CloudWatch alarms | First 10 free, then $0.10 a month each |
| CloudWatch Logs | First 5 GB a month free, then about $0.60 per GB; kept for a month |
| AWS Budgets | First two free |

Two choices are about cost, so keep them. Lambdas run on **ARM64**, about 20% cheaper
than x86. **Every log group has a retention period**, because without one CloudWatch
keeps the logs, and bills for them, forever.

`BaseStack` tags every resource with `Project`, `Environment` (`production`, or `shared`)
and `ManagedBy` (`cdk`). Activate them as cost allocation tags in Billing about a day
after the first deploy (see [The first deploy](#the-first-deploy)): the budget depends on
`Project`. AWS only offers a tag once a resource carries it, and activation is not
retroactive.
