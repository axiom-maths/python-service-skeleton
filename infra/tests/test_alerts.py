from __future__ import annotations

from aws_cdk.assertions import Match

from config import ALERT_EMAIL, ALERTS_TOPIC_PARAMETER, MONTHLY_BUDGET_USD, PROJECT
from stacks.alerts import AlertsStack
from tests.support import template


def test_budget_emails_on_forecast_and_on_actual_spend() -> None:
    t = template(AlertsStack)
    t.has_resource_properties(
        "AWS::Budgets::Budget",
        {
            "Budget": Match.object_like(
                {
                    "BudgetLimit": {"Amount": MONTHLY_BUDGET_USD, "Unit": "USD"},
                    "TimeUnit": "MONTHLY",
                }
            ),
            "NotificationsWithSubscribers": Match.array_with(
                [
                    Match.object_like(
                        {"Notification": Match.object_like({"NotificationType": "FORECASTED"})}
                    ),
                    Match.object_like(
                        {"Notification": Match.object_like({"NotificationType": "ACTUAL"})}
                    ),
                ]
            ),
        },
    )


def test_budget_counts_only_this_projects_spend() -> None:
    # The account is shared with other repositories. Without the filter, this budget
    # would warn about their spend as though it were this Project's.
    template(AlertsStack).has_resource_properties(
        "AWS::Budgets::Budget",
        {
            "Budget": Match.object_like(
                {"CostFilters": {"TagKeyValue": [f"user:Project${PROJECT}"]}}
            )
        },
    )


def test_alert_topic_emails_and_is_published_by_name() -> None:
    t = template(AlertsStack)
    t.has_resource_properties(
        "AWS::SNS::Subscription", {"Protocol": "email", "Endpoint": ALERT_EMAIL}
    )
    # Other stacks find the topic through this parameter; renaming it breaks them at
    # their next deploy, not this one's.
    t.has_resource_properties("AWS::SSM::Parameter", {"Name": ALERTS_TOPIC_PARAMETER})
