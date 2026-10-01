from __future__ import annotations

from aws_cdk.assertions import Match

from stacks.service import ServiceStack
from tests.support import template


def test_function_runs_python_on_arm_with_json_logs() -> None:
    template(ServiceStack).has_resource_properties(
        "AWS::Lambda::Function",
        {
            "Runtime": "python3.14",
            "Architectures": ["arm64"],
            "Handler": "python_service_skeleton.handlers.heartbeat.handler",
            "LoggingConfig": Match.object_like({"LogFormat": "JSON"}),
        },
    )


def test_logs_expire() -> None:
    # Guards against unbounded log retention, which CloudWatch bills for indefinitely.
    template(ServiceStack).has_resource_properties("AWS::Logs::LogGroup", {"RetentionInDays": 30})


def test_both_failure_paths_reach_the_dead_letter_queue() -> None:
    t = template(ServiceStack)
    (queue_id,) = t.find_resources("AWS::SQS::Queue")
    queue_arn = {"Fn::GetAtt": [queue_id, "Arn"]}

    # A handler that raised on every attempt.
    t.has_resource_properties(
        "AWS::Lambda::Function", {"DeadLetterConfig": {"TargetArn": queue_arn}}
    )
    # A schedule that could not deliver at all.
    t.has_resource_properties(
        "AWS::Scheduler::Schedule",
        {"Target": Match.object_like({"DeadLetterConfig": {"Arn": queue_arn}})},
    )


def test_schedule_keeps_london_time() -> None:
    template(ServiceStack).has_resource_properties(
        "AWS::Scheduler::Schedule", {"ScheduleExpressionTimezone": "Europe/London"}
    )


def test_one_dead_letter_raises_the_alarm_and_notifies_someone() -> None:
    template(ServiceStack).has_resource_properties(
        "AWS::CloudWatch::Alarm",
        {
            "MetricName": "ApproximateNumberOfMessagesVisible",
            "Threshold": 1,
            "ComparisonOperator": "GreaterThanOrEqualToThreshold",
            # An alarm with no action reaches nobody.
            "AlarmActions": Match.any_value(),
        },
    )


def test_a_day_without_a_run_raises_the_alarm_and_notifies_someone() -> None:
    template(ServiceStack).has_resource_properties(
        "AWS::CloudWatch::Alarm",
        {
            "MetricName": "Invocations",
            "Statistic": "Sum",
            # Longer than the 25 hours between two Runs when the clocks go back.
            "Period": 26 * 60 * 60,
            "Threshold": 1,
            "ComparisonOperator": "LessThanThreshold",
            # No invocations publish no data, so missing data has to count.
            "TreatMissingData": "breaching",
            "AlarmActions": Match.any_value(),
        },
    )
