# All documentation lives in `docs/`

Every document, infrastructure included (`docs/infra.md`), lives in `docs/`, and every
ADR in `docs/adr/`. One place to look beats documentation that follows the code's
directories. If the infrastructure is ever split out
([ADR-0001](0001-one-repository-infrastructure-in-its-own-uv-project.md)), its page and
the ADRs that still apply are copied across with it, and their links fixed. A split is a
deliberate one-off job, and most decisions go on applying to both repositories
afterwards.

## Considered Options

- *`infra/README.md`,* so that the page moves with `infra/` and GitHub shows it when
  browsing the directory. It could never move unchanged, because it links to ADRs and
  other pages in `docs/` that stay behind. So a split meant fixing links either way, and
  docs lived in two places every day to save part of that work.
- *Infrastructure ADRs in `infra/docs/adr/`.* Turned down for the same reason: decisions
  in two places every day, to save one copy step on a split that may never happen.
