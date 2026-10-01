# One repository, with infrastructure in its own uv project

The application and its infrastructure share a repository, and `infra/` is a separate uv
project with its own `pyproject.toml`, lockfile, virtualenv and tests. With one Project,
a change touching both is one pull request and one CI run. The separate project keeps
`aws-cdk-lib` out of the application, and makes a later split a directory copy.

## Considered Options

- *One project, with CDK in a dependency group.* Simpler now, but a split means
  untangling the configuration by hand.
- *A uv workspace.* Its shared lockfile is exactly what a split has to undo.
- *Separate repositories from the start.* Premature with one Project, and every change
  spanning both becomes two pull requests.
