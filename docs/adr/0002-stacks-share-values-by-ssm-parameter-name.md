# Stacks share values by SSM parameter name, never by reference

A stack that needs another stack's value reads an SSM parameter that the owner
publishes, and a test fails on any `Fn::ImportValue` or `Export`. CloudFormation will
not change or delete an export while anything imports it, which pins the two stacks
together and stops either moving to another repository. A parameter name couples
nothing, and it is how stacks in different repositories have to communicate anyway.

## Considered Options

- *Passing constructs between stacks.* Shorter, and fine for stacks that will always live
  together. The test is the price of keeping the option open.
