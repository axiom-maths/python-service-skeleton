# Each Project owns its alerts stack, budget and alert topic

Each Project deploys its own alerts stack to the Shared target. It holds a monthly budget
filtered to the Project's `Project` cost tag, and the alert topic every alarm in the
Project notifies. Accounts are shared by many repositories. A stack that claimed to be
account-wide, deployed by every Project made from the skeleton, would give the account
one more unfiltered budget and one more "only" alert topic each time. And whichever
repository happened to deploy first would own a parameter that everyone else depends on.

## Considered Options

- *Account-wide, behind a config switch,* so that only the first Project in an account
  deploys it. That leaves the account's alerting owned by whichever repository came
  first, under that Project's parameter names.
- *No budget or topic in the skeleton,* left to an infrastructure repository. A fresh
  Project would then have nothing to send its Alerts to until that repository caught up.

## Consequences

- The budget counts nothing until `Project` is activated as a cost allocation tag, which
  AWS allows only after a resource carries it. Activation is therefore a required step
  of the first deploy, not housekeeping.
- Spend that carries no tag, such as some data transfer, is outside every Project's
  budget. A budget for the whole account belongs to whoever owns the account.
- Different Projects can alert different people, and nothing gives one view of every
  Alert in the account.
