"""Test helpers."""

from __future__ import annotations

import json
from pathlib import Path

import aws_cdk as cdk
from aws_cdk.assertions import Template

from app import build

_CDK_JSON = Path(__file__).resolve().parents[1] / "cdk.json"


def make_app() -> cdk.App:
    """An `App` carrying the same feature flags a real deploy uses.

    A bare `cdk.App()` reads no configuration, so a test app can silently disagree with
    the deployed one about feature flags — and feature flags change what CloudFormation
    receives. Reading `cdk.json` keeps the two honest.
    """
    context = json.loads(_CDK_JSON.read_text())["context"]
    return cdk.App(context=context)


def synth_all() -> dict[str, cdk.Stack]:
    """Every stack `app.py` builds, keyed by stack name."""
    app = make_app()
    build(app)
    return {child.stack_name: child for child in app.node.children if isinstance(child, cdk.Stack)}


def template(stack_class: type[cdk.Stack]) -> Template:
    """The synthesised template of the one stack of this class that `app.py` builds."""
    (stack,) = [s for s in synth_all().values() if isinstance(s, stack_class)]
    return Template.from_stack(stack)
