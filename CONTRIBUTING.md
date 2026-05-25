# Contributing to py-xiaozhi

Looking for the Chinese version? See [CONTRIBUTING_ZH.md](./CONTRIBUTING_ZH.md).

Thank you for helping improve `py-xiaozhi`. We welcome bug reports, documentation fixes, tests, tooling improvements, and well-scoped features.

## Before You Start

- Search existing issues and pull requests before opening a new one.
- Open an issue first for large features, architectural changes, or behavior changes.
- Small bug fixes, docs fixes, and focused improvements can usually go straight to a pull request.

## Development Setup

### Requirements

- Python `>=3.10`
- Git
- A working microphone and speaker if you need to verify audio behavior

### Install Dependencies

```bash
git clone https://github.com/huangjunsen0406/py-xiaozhi.git
cd py-xiaozhi

# Base install
uv sync

# GUI + development tools
uv sync --extra gui --group dev
```

If you do not use `uv`, use the fallback commands below:

```bash
pip install -e .
pip install -e '.[gui]'
pip install pytest pytest-asyncio ruff pyinstaller
```

## Workflow

1. Fork the repository and create a topic branch from `main`.
2. Keep the change focused on one bug, feature, or documentation task.
3. Follow Conventional Commits such as `fix(audio): handle empty frame`.
4. Update docs when behavior, configuration, or public APIs change.
5. Add or update tests when the change affects correctness or regression risk.

Recommended branch names:

- `feature/xxx`
- `fix/xxx`
- `docs/xxx`
- `refactor/xxx`
- `test/xxx`

## Quality Bar

Run the checks that apply to your change before opening a pull request:

```bash
ruff check .
ruff format .
pytest
```

Please also verify the relevant runtime path when applicable, for example:

- GUI changes: launch `python main.py`
- CLI changes: launch `python main.py --mode cli`
- Protocol changes: verify `websocket` or `mqtt` behavior
- Docs changes: preview under `documents/`

## Pull Request Expectations

Each pull request should:

- Explain the problem and the proposed solution clearly.
- Link the related issue when one exists.
- Include validation steps, screenshots, or logs when they help review.
- Stay reasonably small and avoid mixing unrelated refactors.
- Respect the existing coding style and project structure.

## Maintainer Workflow

Maintainers generally review contributions using the following workflow:

1. Triage the change as `bug`, `feature`, `docs`, `refactor`, or `maintenance`.
2. Check whether the scope is clear, reproducible, and aligned with project direction.
3. Review tests, docs, and validation evidence before requesting changes or approval.
4. Merge after CI passes and review feedback is addressed.
5. Ship through the normal release process; merge does not guarantee an immediate release.

## Detailed Guides

- Documentation site: <https://huangjunsen0406.github.io/py-xiaozhi/>
- Detailed contribution guide: <https://huangjunsen0406.github.io/py-xiaozhi/en/contributing>
- Chinese contribution guide: <https://huangjunsen0406.github.io/py-xiaozhi/contributing>

Thanks again for contributing.
