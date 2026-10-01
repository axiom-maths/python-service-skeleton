"""The Project's Alerts: its monthly budget, and the topic every one of its alarms notifies.

Both belong to the whole Project rather than to one Environment, so this stack deploys to
the Shared target: a staging Environment, if one arrives, alarms to the same topic and
spends against the same budget.

Neither is account-wide, though the account is usually shared with other repositories. A
budget for the whole account, and anything else that spans repositories, belongs to
whoever owns the account. See docs/adr/0012-each-project-owns-its-alerts.md.

It publishes the alert topic's ARN to SSM rather than exporting it, so a stack that
alarms reads a parameter name and holds no reference to this stack. That is what lets
the two live in different repositories without either changing. See "The seam between
stacks" in docs/infra.md.
"""

from __future__ import annotations

from typing import Any

from aws_cdk import aws_budgets as budgets
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as subscriptions
from aws_cdk import aws_ssm as ssm
from constructs import Construct

from config import ALERT_EMAIL, ALERTS_TOPIC_PARAMETER, MONTHLY_BUDGET_USD, PROJECT
from stacks.base import BaseStack


class AlertsStack(BaseStack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs: Any) -> None:
        super().__init__(
            scope,
            construct_id,
            description="The Project's budget and alert topic",
            **kwargs,
        )

        # Email, not a topic subscriber: a budget publishing to SNS needs a topic
        # policy admitting budgets.amazonaws.com, and the alert topic gains nothing
        # from carrying both. The first two budgets in an account are free.
        email = budgets.CfnBudget.SubscriberProperty(subscription_type="EMAIL", address=ALERT_EMAIL)
        budgets.CfnBudget(
            self,
            "MonthlyCost",
            budget=budgets.CfnBudget.BudgetDataProperty(
                budget_name=f"{PROJECT}-monthly-cost",
                budget_type="COST",
                time_unit="MONTHLY",
                budget_limit=budgets.CfnBudget.SpendProperty(amount=MONTHLY_BUDGET_USD, unit="USD"),
                # Only this Project's spend, by the `Project` tag BaseStack puts on
                # everything. Unfiltered, it would count every repository's spend in the
                # account. The catch: until `Project` is activated as a cost allocation
                # tag in Billing, AWS attributes nothing to it, so this budget counts $0
                # and can never warn. Activation is a step of the first deploy — see
                # "The first deploy" in docs/infra.md.
                cost_filters={"TagKeyValue": [f"user:Project${PROJECT}"]},
            ),
            notifications_with_subscribers=[
                # Two warnings, because they answer different questions. Forecast
                # fires early in a month that is on course to overspend, while there
                # is still time to act; actual fires once the money is gone.
                budgets.CfnBudget.NotificationWithSubscribersProperty(
                    notification=budgets.CfnBudget.NotificationProperty(
                        notification_type="FORECASTED",
                        comparison_operator="GREATER_THAN",
                        threshold=100,
                        threshold_type="PERCENTAGE",
                    ),
                    subscribers=[email],
                ),
                budgets.CfnBudget.NotificationWithSubscribersProperty(
                    notification=budgets.CfnBudget.NotificationProperty(
                        notification_type="ACTUAL",
                        comparison_operator="GREATER_THAN",
                        threshold=80,
                        threshold_type="PERCENTAGE",
                    ),
                    subscribers=[email],
                ),
            ],
        )

        # One topic for every alarm in the Project, so there is one place to add or
        # remove a person. An alarm with no action is a line on a console nobody
        # opens; this is what makes one reach somebody.
        topic = sns.Topic(self, "Alerts", topic_name=f"{PROJECT}-alerts", enforce_ssl=True)
        topic.add_subscription(subscriptions.EmailSubscription(ALERT_EMAIL))

        ssm.StringParameter(
            self,
            "AlertsTopicArn",
            parameter_name=ALERTS_TOPIC_PARAMETER,
            string_value=topic.topic_arn,
            description="The SNS topic every alarm in this Project notifies",
        )
