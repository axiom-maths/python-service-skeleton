"""An example Service: a scheduled Lambda, whose Failures and Missed runs reach someone.

Replace it with the real thing. It is here so the whole path works before anything
depends on it — code under `src/` packaged as a Lambda, invoked on a schedule, and a
Run that goes wrong becoming an Alert rather than vanishing.

The failure path is the part worth keeping when this is replaced. EventBridge Scheduler
invokes Lambda asynchronously, so a handler that raises is not reported to anybody: Lambda
makes two more Attempts and then, unless told otherwise, discards the event. A Run can go
wrong in three ways:

- the scheduler cannot deliver it (throttled, or its role lost permission), caught by
  the scheduler target's dead-letter queue;
- the handler raised on every Attempt, caught by the function's own dead-letter queue;
- it never happens at all (the schedule was disabled, deleted or broken), which leaves
  no dead letter and is caught only by noticing the absence of Attempts.

The first two are Failures and share one queue, with one alarm on it. A message there will
not recover on its own, so the threshold is one. The third is a Missed run, with an alarm
of its own.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import aws_cdk as cdk
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_cloudwatch_actions as cloudwatch_actions
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_scheduler as scheduler
from aws_cdk import aws_scheduler_targets as targets
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sqs as sqs
from aws_cdk import aws_ssm as ssm
from constructs import Construct

from config import ALERTS_TOPIC_PARAMETER, PROJECT
from stacks.base import BaseStack

# The application's source. The Lambda asset is this directory as it stands: the
# handler's import path below is relative to it.
SOURCE = Path(__file__).resolve().parents[2] / "src"


class ServiceStack(BaseStack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs: Any) -> None:
        super().__init__(
            scope,
            construct_id,
            description="Example service: a scheduled Lambda with a dead-letter queue",
            **kwargs,
        )
        environment_name = self.target.name

        dead_letters = sqs.Queue(
            self,
            "DeadLetters",
            queue_name=f"{PROJECT}-dead-letters-{environment_name}",
            # The longest SQS allows: a failure noticed on a Monday after a holiday
            # should still be there to read.
            retention_period=cdk.Duration.days(14),
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            enforce_ssl=True,
        )

        function = lambda_.Function(
            self,
            "Heartbeat",
            function_name=f"{PROJECT}-heartbeat-{environment_name}",
            # Arm, because it is about 20% cheaper than x86 for the same work, and
            # it is what an Apple Silicon laptop builds natively.
            runtime=lambda_.Runtime.PYTHON_3_14,
            architecture=lambda_.Architecture.ARM_64,
            handler="python_service_skeleton.handlers.heartbeat.handler",
            code=lambda_.Code.from_asset(str(SOURCE), exclude=["**/__pycache__", "*.pyc"]),
            timeout=cdk.Duration.seconds(10),
            memory_size=128,
            environment={"ENVIRONMENT": environment_name},
            # JSON lines, so `extra=` fields on a log call arrive as fields that Logs
            # Insights can filter on, rather than as text inside a message.
            logging_format=lambda_.LoggingFormat.JSON,
            log_group=logs.LogGroup(
                self,
                "HeartbeatLogs",
                log_group_name=f"/{PROJECT}/{environment_name}/heartbeat",
                # Logs are billed for as long as they are kept. A month covers
                # noticing a problem and looking back at it.
                retention=logs.RetentionDays.ONE_MONTH,
                removal_policy=cdk.RemovalPolicy.DESTROY,
            ),
            dead_letter_queue=dead_letters,
            retry_attempts=2,
        )

        # The Missed-run alarm below assumes one Run a day: change one, change the other.
        scheduler.Schedule(
            self,
            "Daily",
            schedule_name=f"{PROJECT}-heartbeat-{environment_name}",
            description="Runs the heartbeat every morning",
            # A time zone, not UTC: "7am" should mean 7am in London on both sides of
            # the clocks changing.
            schedule=scheduler.ScheduleExpression.cron(
                minute="0", hour="7", time_zone=cdk.TimeZone.EUROPE_LONDON
            ),
            target=targets.LambdaInvoke(
                function,
                dead_letter_queue=dead_letters,
                input=scheduler.ScheduleTargetInput.from_object(
                    {"scheduled_time": scheduler.ContextAttribute.scheduled_time}
                ),
            ),
        )

        # Resolved by CloudFormation at deploy time from the parameter the account
        # stack publishes. A name, not a reference to that stack: see
        # stacks/alerts.py.
        alerts = sns.Topic.from_topic_arn(
            self,
            "Alerts",
            ssm.StringParameter.value_for_string_parameter(self, ALERTS_TOPIC_PARAMETER),
        )

        alarm = cloudwatch.Alarm(
            self,
            "DeadLettersAlarm",
            alarm_name=f"{PROJECT}-dead-letters-{environment_name}",
            alarm_description="A Run failed every Attempt. Read the dead letters.",
            metric=dead_letters.metric_approximate_number_of_messages_visible(
                period=cdk.Duration.minutes(5), statistic="Maximum"
            ),
            threshold=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            evaluation_periods=1,
            # No data means an empty queue, which is the healthy state.
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        alarm.add_alarm_action(cloudwatch_actions.SnsAction(alerts))

        missed_run = cloudwatch.Alarm(
            self,
            "MissedRunAlarm",
            alarm_name=f"{PROJECT}-missed-run-{environment_name}",
            alarm_description=(
                "No Run has started in 26 hours. Check the schedule is enabled and can "
                "invoke the function."
            ),
            # Every Attempt counts, failed or not: failed ones are the dead-letter
            # alarm's business, and this one only asks whether anything started.
            # 26 hours rather than 24: when the clocks go back, two 7am Runs are 25
            # hours apart, and the extra hour absorbs metric delay. A sliding window
            # (the default), so it is the last 26 hours, not calendar days.
            metric=function.metric_invocations(period=cdk.Duration.hours(26), statistic="Sum"),
            threshold=1,
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
            evaluation_periods=1,
            # Lambda publishes nothing when nothing runs, so no data is the very thing
            # being watched for. One consequence: straight after the first deploy the
            # window is empty and this goes into alarm until the first Run. Nobody is
            # told, because the email subscription is not confirmed yet and an alarm
            # notifies only when its state changes.
            treat_missing_data=cloudwatch.TreatMissingData.BREACHING,
        )
        missed_run.add_alarm_action(cloudwatch_actions.SnsAction(alerts))
