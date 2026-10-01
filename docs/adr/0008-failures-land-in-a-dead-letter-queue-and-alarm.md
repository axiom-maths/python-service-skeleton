# Failures land in a dead-letter queue, and Missed runs raise their own alarm

The scheduler failing to deliver a Run and the handler failing every Attempt both feed
one dead-letter queue. One alarm watches it with a threshold of one. A second alarm fires
when no Attempt at all has started in 26 hours. Both notify the alert topic. An
asynchronously invoked Lambda retries twice and then, by default, drops the event
silently, and an alarm with no action notifies nobody. A Run that never happens leaves no
dead letter, so it can only be caught by its absence.

## Consequences

- The Missed-run alarm treats missing data as breaching, because Lambda publishes
  nothing when nothing runs. It is in alarm from the first deploy until the first Run.
  Nobody is told, because the email subscription is not yet confirmed and an alarm
  notifies only when its state changes.
- Its window assumes one Run a day: 26 hours covers the 25-hour gap when the clocks go
  back. A different schedule needs a different window.
- Disabling the schedule on purpose Alerts the next day, as a reminder to turn it back
  on.

## Considered Options

- *A 48-hour window,* which stays quiet after the first deploy but doubles the time to
  notice a real Missed run for the life of the Project.
