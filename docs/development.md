# Development

Day-to-day work in the repository. Deploying is covered in
[infra.md](infra.md).

## Two uv projects

The root is the application (`src/`, `tests/`). `infra/` is a separate uv project with
its own `pyproject.toml`, lockfile, virtualenv and tests. That keeps `aws-cdk-lib` out
of the application, and lets `infra/` become its own repository by being copied out
([ADR-0001](adr/0001-one-repository-infrastructure-in-its-own-uv-project.md)). The
two never import each other.

The `Makefile` runs every check over both. To add a dependency, run `uv add` in the
project that imports it:

```bash
uv add --dev hypothesis            # the application
cd infra && uv add cdk-nag         # the infrastructure
```

The ruff and mypy settings are repeated in both `pyproject.toml` files. Keep them in
step.

## Checks

```bash
make ci           # lint, typecheck, test and synth over both projects
make format       # fix formatting and auto-fixable lint

uv run pytest tests/test_heartbeat.py
cd infra && uv run pytest tests/test_service.py -k alarm
```

CI runs the same checks on every pull request, with no AWS credentials.

## Writing a handler

Copy the shape of `src/python_service_skeleton/handlers/heartbeat.py`:

- **Keep the entry point thin.** It reads its configuration, calls a plain function and
  logs the result. Tests call the plain function, with no AWS involved.
- **Take configuration from environment variables** that the stack sets, never from AWS
  at runtime.
- **Raise on bad input.** In an asynchronous Lambda, an exception sends the event to the
  dead-letter queue and fires the alarm. Returning quietly looks like success.
- **Log an event name, with the detail in `extra`.** Logs are JSON, so each key becomes
  a field that CloudWatch Logs Insights can filter on.

## Adding a stack

1. Write `infra/stacks/<thing>.py` as a subclass of `BaseStack`. It pins the stack to a
   `Target` from `config.py`, and tags it.
2. Create it in `infra/app.py`, named `target.stack_name("<thing>")`.
3. If the pipeline should deploy it, add it to `STACKS` in the `Makefile`.
4. Test it in `infra/tests/test_<thing>.py`.

To use a value another stack owns, publish it as an SSM parameter under
`target.parameter_name(...)` and read it by name. See
[The seam between stacks](infra.md#the-seam-between-stacks).

**Set `removal_policy=RemovalPolicy.RETAIN` explicitly on anything holding data you
cannot recreate,** even where it is the default. CDK's defaults vary by resource, and
being explicit makes the choice visible in review.

### Testing a stack

Build the template with `template(YourStack)` from `infra/tests/support.py`, which
applies the feature flags in `cdk.json`. A bare `cdk.App()` applies none of them, so it
can disagree with a real deploy. Assert on template properties, not on logical ids,
which contain generated hashes.

`infra/tests/test_app.py` checks every stack's naming, description and tags, and that
no stack exports or imports a value. New stacks are covered automatically.

## Adding a runtime dependency

`src/` ships to Lambda as it is, and the Lambda runtime provides only the standard
library and `boto3`. That is why `dependencies` in `pyproject.toml` is empty. A package
added with `uv add` passes the tests, and fails in Lambda with `ModuleNotFoundError`.

When the first dependency arrives, pick a way to package it:

- **Bundle it into the function's asset** (the usual choice). Give `Code.from_asset`
  bundling options that run `uv pip install --target`. uv can fetch Linux arm64 wheels
  from a Mac (`--python-platform aarch64-manylinux2014 --python-version 3.14
  --only-binary :all:`), so no Docker is needed.
- **A Lambda layer**, when several functions share the same dependencies.
- **A container image** (`DockerImageFunction`), past Lambda's 250 MB unzipped limit.

For a plain HTTPS call, `urllib.request` may be enough.

## Secrets

Keep an API key or password in SSM Parameter Store as a `SecureString`, created by hand
so that the value never appears in the repository or a template:

```bash
printf 'Value: '; read -rs VALUE; echo
aws ssm put-parameter --name /<project>/production/<name> --type SecureString --value "$VALUE"
unset VALUE
```

Then grant the function `ssm:GetParameter` on that parameter (and `kms:Decrypt` for a
customer-managed key). Pass it the parameter's **name** as an environment variable, and
read the value once per cold start.

Never put a secret's value in an environment variable, a template, a log or command
output. Once it has been printed, the only fix is to rotate it.
