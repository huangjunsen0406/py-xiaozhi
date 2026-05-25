---
title: Contributing
description: How to contribute to py-xiaozhi
sidebar: false
outline: deep
---

# Contributing

Chinese version: [简体中文](/contributing)

Thank you for contributing to `py-xiaozhi`. This guide explains how we expect issues, pull requests, review cycles, and maintainer handoff to work.

## What We Welcome

We welcome:

- Bug reports with clear reproduction steps
- Documentation fixes and examples
- Tests and tooling improvements
- Focused features that fit the project roadmap
- Small refactors that reduce complexity without changing behavior

For large feature requests, architectural changes, or behavior changes, please open an issue first so the scope can be discussed before implementation.

## Development Setup

### Requirements

- Python `>=3.10`
- Git
- A usable microphone and speaker when validating audio-related changes

### Clone and Install

```bash
git clone https://github.com/huangjunsen0406/py-xiaozhi.git
cd py-xiaozhi

# Base install
uv sync

# GUI + development tools
uv sync --extra gui --group dev
```

If you do not use `uv`, you can use the fallback path:

```bash
pip install -e .
pip install -e '.[gui]'
pip install pytest pytest-asyncio ruff pyinstaller
```

## Working on a Change

### Branching

Create a topic branch from `main`:

```bash
git checkout -b fix/your-change main
```

Recommended branch prefixes:

- `feature/xxx`
- `fix/xxx`
- `docs/xxx`
- `refactor/xxx`
- `test/xxx`

### Commit Messages

We follow Conventional Commits:

```text
<type>[optional scope]: <description>
```

Examples:

- `fix(audio): avoid empty opus frame`
- `docs(readme): clarify gui install`
- `refactor(protocol): simplify reconnect flow`

## Quality Checks

Run the checks that apply to your change before opening a pull request:

```bash
ruff check .
ruff format .
pytest
```

Validate the runtime path that matches your change:

- GUI changes: `python main.py`
- CLI changes: `python main.py --mode cli`
- MQTT changes: `python main.py --protocol mqtt`
- Docs changes:

```bash
cd documents
pnpm install
pnpm docs:dev
```

## Pull Request Expectations

A good pull request is usually:

- Focused on one topic
- Easy to review commit by commit
- Clear about the problem being solved
- Explicit about validation steps
- Updated with docs when behavior or configuration changes

Please include the following in the PR description when relevant:

- Why the change is needed
- What changed
- How you verified it
- Screenshots, logs, or recordings for UI and behavior changes
- Related issue links

## Review Policy

Maintainers generally review pull requests using these criteria:

1. Scope is clear and aligned with project goals.
2. The change is reproducible, testable, and technically sound.
3. The implementation fits existing architecture and coding style.
4. Docs and validation evidence are present when needed.
5. Review feedback has been addressed without introducing unrelated churn.

## Maintainer Workflow

The typical maintainer workflow is:

1. Triage the incoming change as `bug`, `feature`, `docs`, `refactor`, or `maintenance`.
2. Confirm that the problem statement and scope are complete enough to review.
3. Request changes when tests, docs, or validation evidence are missing.
4. Merge after CI passes and review feedback is resolved.
5. Ship through the normal release flow; merge does not guarantee an immediate release.

## Issue Reporting

Please use the existing GitHub issue templates whenever possible:

- Bug report
- Feature request
- Documentation improvement
- Code improvement

When opening an issue, include:

- Expected behavior
- Actual behavior
- Reproduction steps
- OS and Python version
- Logs, stack traces, or screenshots when useful

## Documentation Contributions

Documentation lives under `documents/docs`.

For docs-only contributions:

1. Keep wording direct and task-oriented.
2. Prefer runnable commands and concrete examples.
3. Update both English and Chinese pages when content is intended to stay in sync.
4. Preview the VitePress site locally before opening the PR.

## Related Entry Points

- Repository workflow: [CONTRIBUTING.md](https://github.com/huangjunsen0406/py-xiaozhi/blob/main/CONTRIBUTING.md)
- Chinese repository workflow: [CONTRIBUTING_ZH.md](https://github.com/huangjunsen0406/py-xiaozhi/blob/main/CONTRIBUTING_ZH.md)
- Project documentation: <https://huangjunsen0406.github.io/py-xiaozhi/>
