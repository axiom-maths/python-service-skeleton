"""Properties of the app as a whole, rather than of any one stack."""

from __future__ import annotations

import json

from aws_cdk.assertions import Template

from config import GITHUB_REPOSITORY, PROJECT
from tests.support import synth_all


def test_every_stack_is_named_for_the_project() -> None:
    for name in synth_all():
        assert name.startswith(f"{PROJECT}-")


def test_no_stack_references_another() -> None:
    # The seam that lets a stack move to another repository unchanged. A construct
    # passed from one stack to another becomes an Export and an Fn::ImportValue, and
    # CloudFormation then refuses to change or delete the exporting stack while the
    # importer exists — even from a different repository, which has no way to see why.
    # Stacks share values through SSM parameter names instead. If this fails, publish
    # the value as a parameter rather than passing the construct.
    for name, stack in synth_all().items():
        body = json.dumps(Template.from_stack(stack).to_json())
        assert "Fn::ImportValue" not in body, f"{name} imports from another stack"
        assert '"Export"' not in body, f"{name} exports to another stack"


def test_every_stack_says_where_its_code_lives() -> None:
    for stack in synth_all().values():
        assert stack.template_options.description is not None
        assert stack.template_options.description.endswith(f"Managed by {GITHUB_REPOSITORY}.")


def test_cost_allocation_tags_reach_resources() -> None:
    checked = 0
    for stack in synth_all().values():
        for resource in Template.from_stack(stack).to_json()["Resources"].values():
            tags = resource.get("Properties", {}).get("Tags")
            # Only list-shaped tags are checked; a few resource types take a map, and
            # some cannot be tagged at all.
            if not isinstance(tags, list):
                continue
            keys = {tag["Key"] for tag in tags}
            assert {"Project", "Environment", "ManagedBy"} <= keys, resource["Type"]
            checked += 1
    assert checked, "no taggable resources found, so nothing was checked"
