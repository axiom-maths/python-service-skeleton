# The developer interface. `make help` lists every target.
#
# Two uv projects live here: the application at the root, and the infrastructure in
# infra/. Each quality target runs over both, so `make ci` is one command either way.
#
# Nothing here names an AWS profile. Every target uses whatever credentials the shell
# already has — `[default]`, or `AWS_PROFILE=… make deploy` as a per-command override.
# Profile names belong to a laptop, not to a repository: see docs/aws-access.md.

PROJECT := python-service-skeleton

# Where everything is. Pinned here because it is a fact about the project, not about a
# laptop; still overridable.
AWS_REGION ?= eu-west-2
export AWS_REGION

# The CDK CLI is a Node package (aws-cdk-lib provides no `cdk` binary), pinned in
# infra/package.json and run from there, so everyone runs the same version and nobody
# needs a global install. cdk.json points it back at `uv run python app.py`.
CDK := npx --no-install cdk

# The stacks the pipeline deploys. Not the deploy stack: that holds the pipeline's own
# credentials, and is deployed by hand with `make deploy-github-role`.
STACKS ?= $(PROJECT)-alerts-shared $(PROJECT)-service-production

# Extra flags for `cdk deploy`. Empty at a laptop, where the prompt before an IAM change
# is worth answering; the deploy workflow passes `--require-approval never`, since
# nobody is there to answer it and review happened on the pull request.
CDK_FLAGS ?=

# Hands the CDK CLI credentials resolved by the AWS CLI, rather than letting it walk the
# credential chain itself. The CDK is Node, and its chain is fussier about ~/.aws/config
# than the AWS CLI's — it rejects some SSO configurations the CLI accepts — so this makes
# the two agree. `make synth` makes no AWS calls and needs none of it.
with_aws_creds = eval "$$(aws configure export-credentials --format env)" && $(1)

.DEFAULT_GOAL := help

# --- Setting up ---------------------------------------------------------------

.PHONY: install
install: ## Install both projects' dependencies and the pinned CDK CLI
	uv sync
	cd infra && uv sync
	cd infra && npm ci --silent

# --- Quality ------------------------------------------------------------------

.PHONY: lint
lint: ## Check formatting and lint, in both projects
	uv run ruff format --check .
	uv run ruff check .
	cd infra && uv run ruff format --check .
	cd infra && uv run ruff check .

.PHONY: format
format: ## Fix formatting and auto-fixable lint, in both projects
	uv run ruff format .
	uv run ruff check --fix .
	cd infra && uv run ruff format .
	cd infra && uv run ruff check --fix .

.PHONY: typecheck
typecheck: ## mypy --strict, in both projects
	uv run mypy
	cd infra && uv run mypy

.PHONY: test
test: ## Every test, in both projects
	uv run pytest
	cd infra && uv run pytest

.PHONY: ci
ci: lint typecheck test synth ## Everything CI runs

# --- Infrastructure -----------------------------------------------------------

.PHONY: synth
synth: ## Synthesise the CloudFormation templates (needs no AWS credentials)
	cd infra && $(CDK) synth --quiet

.PHONY: bootstrap
bootstrap: sso ## Once per account and region: the bucket and roles the CDK deploys with
	@# With no environment named, `cdk bootstrap` bootstraps every account and region
	@# the app's stacks name — so it reads them from infra/config.py, not from here.
	cd infra && $(call with_aws_creds,$(CDK) bootstrap)

.PHONY: diff
diff: sso ## What a deploy would change (STACKS=… to narrow)
	cd infra && $(call with_aws_creds,$(CDK) diff $(STACKS))

.PHONY: deploy
deploy: sso ## Deploy the pipeline's stacks (STACKS=… to narrow). Normally CI does this.
	cd infra && $(call with_aws_creds,$(CDK) deploy $(CDK_FLAGS) $(STACKS))

# --- The deployment pipeline --------------------------------------------------

# Both run once, by hand, as an administrator, and are what let GitHub Actions deploy.
# A pipeline cannot create the credentials it runs with.

.PHONY: github-oidc-provider
github-oidc-provider: sso ## Register GitHub as an OIDC provider (account-wide; safe to re-run)
	@# IAM allows one provider per issuer per account, shared by every repository that
	@# deploys into it — so it is created here rather than owned by any stack, where a
	@# `cdk destroy` would take it from everyone. Idempotent: reports an existing one.
	@# No thumbprint: AWS verifies GitHub's certificate against its own trusted CAs.
	@ARN=$$(aws iam list-open-id-connect-providers \
		--query "OpenIDConnectProviderList[?ends_with(Arn, ':oidc-provider/token.actions.githubusercontent.com')].Arn | [0]" \
		--output text); \
	if [ -n "$$ARN" ] && [ "$$ARN" != None ]; then \
		echo "already registered: $$ARN"; \
	else \
		aws iam create-open-id-connect-provider \
			--url https://token.actions.githubusercontent.com \
			--client-id-list sts.amazonaws.com \
			--query OpenIDConnectProviderArn --output text; \
	fi

.PHONY: deploy-github-role
deploy-github-role: sso github-oidc-provider ## Deploy the role GitHub Actions assumes (once)
	cd infra && $(call with_aws_creds,$(CDK) deploy $(CDK_FLAGS) $(PROJECT)-deploy-production)

# --- AWS ----------------------------------------------------------------------

.PHONY: sso
sso: ## Log in to AWS SSO if the session has expired
	@# Tests whether you are authenticated, not whether a profile variable is set: a
	@# working `[default]` needs neither. In CI, credentials come from OIDC and there is
	@# no browser to log in with, so fail at once rather than wait on one.
	@aws sts get-caller-identity --no-cli-pager >/dev/null 2>&1 && exit 0; \
	if [ -n "$$CI" ]; then \
		echo "no usable AWS credentials, and this is CI: check the credentials step"; \
		exit 1; \
	fi; \
	aws sso login

# --- Help ---------------------------------------------------------------------

.PHONY: help
help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'
