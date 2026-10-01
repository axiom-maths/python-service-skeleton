# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Python service on AWS. The application is in `src/`. Its infrastructure is CDK Python
in `infra/`. Started from
[axiom-maths/python-service-skeleton](https://github.com/axiom-maths/python-service-skeleton).
`docs/development.md` covers day-to-day work and the conventions, `docs/infra.md`
covers deploying, and the ADRs in `docs/adr/` record why things are shaped as they are.

The project's vocabulary is defined in `CONTEXT.md`, imported below. Use its terms in
code, comments and docs, and avoid the words it lists under _Avoid_.

@CONTEXT.md

## Commands

```bash
make install       # both uv projects, and the pinned CDK CLI
make ci            # lint + typecheck + test + synth, for both projects. Run before every commit.
make format        # fix formatting and auto-fixable lint
make synth         # templates only; needs no AWS credentials

uv run pytest tests/test_heartbeat.py                    # one application test file
cd infra && uv run pytest tests/test_service.py -k alarm # one infra test
```

`make diff` and `make deploy` need AWS credentials. Normally a merge to `main` deploys.
Do not deploy unless asked: hand over the commands instead.

## Two uv projects

The root is the application. `infra/` is a separate uv project: its own
`pyproject.toml`, `uv.lock`, `.venv` and tests. Run infra commands from `infra/`, or
through `make`. Add a dependency to the project that imports it (`uv add` at the root,
or `cd infra && uv add`). Never import across the two. Infra refers to the application
only as a directory path, for the Lambda asset.

## Conventions

- Python 3.14, `uv` for everything, `ruff` for lint and format, `mypy --strict`.
- Every stack subclasses `infra/stacks/base.py:BaseStack` and is bound to a `Target`
  from `infra/config.py`. Names, the account and the region live in `config.py` and
  nowhere else.
- Stacks never pass constructs to each other. Share a value by publishing an SSM
  parameter under `Target.parameter_name(...)` and reading it by name.
  `infra/tests/test_app.py` fails on any cross-stack export. Do not "fix" that by
  weakening the test: it is what lets a stack move to another repository.
- Infra tests get templates through `tests/support.py` (`template(Stack)`), which
  applies `cdk.json`'s feature flags. Assert on template properties, not logical ids.
- Lambda handlers stay thin: read environment variables, call a plain function, log.
  Put the logic where a test can call it with no AWS.
- Comments explain *why*, especially where a choice looks odd. Keep them when editing.
- Record decisions, and the alternatives turned down, as ADRs in `docs/adr/`
  (`NNNN-slug.md`, the next number). A project started from the skeleton keeps the
  skeleton's ADRs and adds its own. When a decision changes, edit its ADR, or mark it
  `superseded by ADR-NNNN` in a Status frontmatter.
- Define a new domain term in `CONTEXT.md` when it settles. It is a glossary only,
  with no implementation detail.

## Traps

- **Never name an AWS profile in this repository.** No `AWS_PROFILE=` default, no
  `--profile` flag in the Makefile or scripts, no check that a profile is set. Use
  ambient credentials. To test for a session, run
  `aws sts get-caller-identity >/dev/null 2>&1 || aws sso login`.
- **`cdk synth` must stay credential-free.** No `from_lookup`, no `Vpc.from_lookup`,
  no reading SSM at synth time. Resolve at deploy time instead
  (`StringParameter.value_for_string_parameter`, dynamic references). CI's synth step
  has no credentials and will fail if this regresses.
- **`src/` ships to Lambda as it is.** Only the standard library and `boto3` are
  available at runtime. Adding a package to `dependencies` makes it importable in
  tests and broken in Lambda. See "Adding a runtime dependency" in docs/development.md.
- **mypy and `cdk.out`.** Synth copies `src/` into `infra/cdk.out/asset.*/`. The infra
  mypy config excludes it. Keep that exclusion.
- **The OIDC provider is not in CDK** (`make github-oidc-provider`): there is one per
  account, shared by every repository. Never add it to a stack.
- **The deploy role trusts two spellings of the repository.** A subject mismatch
  gives `Not authorized to perform sts:AssumeRoleWithWebIdentity`, which looks like a
  missing role. Check `gh api repos/<owner>/<repo>/actions/oidc/customization/sub`
  against `GITHUB_REPOSITORY_IMMUTABLE` in `infra/config.py` before suspecting the role.
- **Retain what cannot be recreated.** A bucket or table of real data takes
  `removal_policy=RemovalPolicy.RETAIN`.

## Secrets

Never put a secret's value into command output: not an API key, not a parameter fetched
with `--with-decryption`. Anything printed reaches the session transcript, and after
that the only fix is rotating the credential. Read names, never values. If a secret is
printed anyway, say so at once, name it, and give the steps to rotate it.
