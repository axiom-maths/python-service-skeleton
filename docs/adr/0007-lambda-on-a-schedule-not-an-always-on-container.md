# Lambda on a schedule, not an always-on container

The example Service is a Lambda invoked by EventBridge Scheduler. Short scheduled or
event-driven work is free at this scale on Lambda, while an always-on Fargate task costs
about $15–20 a month whether it has work or not.

## Considered Options

- *Fargate.* The right choice for work longer than Lambda's 15 minutes, or for something
  that holds connections open, such as a long-running queue consumer.
