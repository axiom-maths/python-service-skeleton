# The CDK CLI is pinned in `infra/package.json`

The CDK CLI runs as `npx --no-install cdk` from `infra/node_modules`, with nothing
installed globally. Everyone, CI included, runs the same version, and it stays
compatible with `aws-cdk-lib`. Global installs drift from laptop to laptop.
