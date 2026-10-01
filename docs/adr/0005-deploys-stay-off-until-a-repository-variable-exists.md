# Deploys stay off until a repository variable exists

The deploy job runs only when `DEPLOY_ROLE_ARN` is set. A fresh copy has no AWS account:
without the guard every merge would fail, and a pipeline that always fails gets ignored.
The ARN is a variable rather than a secret because it grants nothing without a token the
trust policy accepts.
