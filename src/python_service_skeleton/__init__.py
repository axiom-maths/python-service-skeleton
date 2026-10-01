"""The application: the code that runs, as opposed to infra/, which says where it runs.

Everything under src/ is shipped to Lambda as it stands, so nothing here may import from
infra/ or from tests/, and a third-party dependency must be packaged with it before it
can be imported — see "Adding a runtime dependency" in docs/development.md.
"""
