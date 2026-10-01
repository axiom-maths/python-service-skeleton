# AWS access

Every command that talks to AWS uses the credentials your shell already has. The
repository never sets or checks a profile name. Profile names are a choice made on each
laptop, and hardcoding one breaks for everyone who named theirs differently. The region
is part of the project, so it is pinned in the `Makefile` and `infra/config.py`.

CI holds no AWS keys: see [the deployment pipeline](infra.md#the-deployment-pipeline).

## Profiles

Access is through IAM Identity Center (SSO), with two permission sets: read-only for
everyday use, and administrator for changes. In `~/.aws/config`:

```ini
[sso-session main]
sso_start_url = https://<something>.awsapps.com/start
sso_region = eu-west-2
sso_registration_scopes = sso:account:access

[default]
sso_session = main
sso_account_id = <account id>
sso_role_name = <read-only permission set>
region = eu-west-2

[profile admin]
sso_session = main
sso_account_id = <account id>
sso_role_name = AdministratorAccess
region = eu-west-2
```

```bash
aws sso login --sso-session main
aws sts get-caller-identity                    # read-only
aws sts get-caller-identity --profile admin    # administrator
```

A few details matter:

- **The default profile is read-only,** so a mistyped command cannot change anything.
- **`[default]`, not `[profile default]`.** It is the only section without the prefix.
- **Both profiles share one `sso-session`,** so one login serves both. Give the session
  a bare name: the CDK rejects some quoted names that the AWS CLI accepts.
- **No `~/.aws/credentials` file.** A stray key pair there, often left by an IDE plugin,
  overrides SSO and causes `InvalidClientTokenId`.

## Escalating

Escalate one command at a time, not for a whole shell:

```bash
AWS_PROFILE=admin make deploy
```

An `export AWS_PROFILE=admin` left in a shell for hours is how something consequential
gets done as an administrator by mistake. A prompt that shows the active profile helps.

## When credentials expire

Run `aws sso login --sso-session main`. Every `make` target that needs AWS does this for
you through `make sso`, but only when the session has expired.
