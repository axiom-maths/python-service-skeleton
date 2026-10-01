# The GitHub OIDC provider is created by a make target, not a stack

`make github-oidc-provider` creates the provider idempotently, and stacks build its ARN
from the account id. IAM allows one provider per issuer per account, shared by every
repository that deploys there. If a stack owned it, a second repository's stack would
fail with `EntityAlreadyExists`, and a `cdk destroy` would break every other
repository's deploys. Building the ARN rather than looking it up keeps `cdk synth`
credential-free.

## Considered Options

- *An account-level stack.* Right once there is an infrastructure repository to hold it
  (see [Splitting infrastructure out](../infra.md#splitting-infrastructure-out)).
