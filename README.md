# Nocturne Inspector

Engineering Intelligence Engine.

Nocturne Inspector performs software engineering analysis before implementation begins.

It produces deterministic, evidence-based reports. The current milestone inspects
essential project documentation; additional specialists remain roadmap work.

The Inspector never modifies the project it analyzes.

It understands software.

The Nocturne Codex consumes this intelligence to plan and implement changes.

## Requirements

- Python 3.13 or newer

## Command line

Inspect a project and print its JSON report to standard output:

```shell
nocturne-inspector inspect PATH
```

Save the report only when an explicit destination is provided:

```shell
nocturne-inspector inspect PATH --format json --output report.json
```

Analysis itself creates no files or directories. Report serialization is a separate
operation, does not create missing parent directories, and refuses to overwrite an
existing destination.

Use `nocturne-inspector --help` for command help and
`nocturne-inspector --version` for the installed version.

## Development validation

Install the project with its development tools, then run all configured checks:

```shell
python -m pip install -e '.[dev]'
ruff format --check .
ruff check .
mypy
python -m unittest discover -s tests -v
python -m pip wheel --no-deps --wheel-dir /tmp/nocturne-dist .
```
