# Python service skeleton

One Project: a Service on AWS, the infrastructure that runs it, and the path by which
its Failures and Missed runs reach a person.

## Language

### What gets deployed, and where

**Project**:
One repository and everything it deploys. Its name prefixes everything it owns.
_Avoid_: repo name, product, app

**Service**:
The Project's application code together with the resources that run it. A Project has
one Service; a second scheduled function is more of the same Service, not a second one.
_Avoid_: app, function, the Lambda

**Target**:
A named place a stack deploys to: an account, a region and a name.
_Avoid_: stage, deployment

**Environment**:
A Target that runs the Service, such as production or staging. It is also the name of
the GitHub environment that gates deploys to it.
_Avoid_: stage, env

**Shared**:
The Target for what all of a Project's Environments use, such as its Alert topic and
its budget. It is never an Environment itself: no Service runs there.
_Avoid_: global, account-wide, common

**Deploy role**:
The identity that the Project's pipeline assumes to deploy into one Environment.
There is one per Project and Environment, never shared.
_Avoid_: CI user, deploy key

### When things go wrong

**Run**:
One scheduled invocation of the Service.
_Avoid_: job, execution

**Attempt**:
One try at a Run. A Run gets three Attempts before it is given up on.
_Avoid_: retry (that is only an Attempt after the first)

**Failure**:
A Run whose every Attempt failed, or that could not be delivered at all. A Run that
succeeds on a later Attempt is not a Failure.
_Avoid_: error

**Missed run**:
A Run that was due and never got an Attempt. Unlike a Failure, it leaves no Dead
letter, so it is noticed by its absence.
_Avoid_: skipped run, silent failure

**Dead letter**:
The record of a Failure, kept until someone reads it.
_Avoid_: failed message

**Alarm**:
A watched condition that is either healthy or not.
_Avoid_: alert, monitor

**Alert**:
Any message that reaches a person because something needs attention, whether from an
Alarm or from a budget warning.
_Avoid_: notification, page

**Alert topic**:
Where Alarms send their Alerts: the one place to add or remove a person.
_Avoid_: alarm topic, notification channel
