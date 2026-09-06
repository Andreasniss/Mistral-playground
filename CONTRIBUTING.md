# Contributing

Read [README.md](README.md) for prerequisites and the supported project scope,
[AGENTS.md](AGENTS.md) for repository instructions, and [PRIVACY.md](PRIVACY.md)
before uploading public changes. Use fictional examples and keep credentials and
private working material outside the repository.

## Verify a change

Run from the repository root with the documented runtime:

```sh
uv sync --locked --dev
uv run ruff check .
uv run pytest -q
uv run python -m evals.run_evals
python3 scripts/check_privacy.py --staged
python3 scripts/check_privacy.py --range origin/main HEAD
```

Include the problem, scoped change, actual checks and affected revision in a focused
pull request. Add regression coverage for behavior changes and preserve documented
limitations. Required CI must pass before merge. Documentation-only changes should
verify links and licensing consistency without claiming application behavior tests
that were not run.

## Licensing and reporting

Submit only work you have the right to contribute. Contributions intended for
inclusion follow [Apache-2.0](LICENSE), unless explicitly agreed otherwise. Preserve
third-party license and copyright notices; identify copied material and its source.
Report sensitive vulnerabilities through [SECURITY.md](SECURITY.md), not a public
issue. Ordinary bugs and improvements can use this repository's GitHub issues.
