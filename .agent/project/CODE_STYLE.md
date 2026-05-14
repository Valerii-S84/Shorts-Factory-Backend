# CODE_STYLE

Заповнюй тільки мовно-специфічні правила цього репозиторію.

Не дублюй тут правила з `.agent/core/PRINCIPLES.md`.
Невикористані секції позначай як `Not used in this repo.`

primary_language: Python
active_sections: Python, SQL, Shell, Tests and fixtures
fallback: якщо стек зміниться, онови цей файл перед застосуванням стилю.

## Active languages

- Languages in scope: Python, SQL, Shell

## Python

- Formatter: Ruff formatter preferred after tooling is configured.
- Linter: Ruff preferred after tooling is configured.
- Type checker: Pyright or mypy to be selected during scaffolding; public service contracts should use explicit Pydantic models.
- Import/order rules: standard library, third-party, local imports in separate groups; avoid side-effect imports.
- Line length / docstring limits: 100 characters preferred after tooling is configured; docstrings explain public contracts and non-obvious constraints.
- Python-specific test rules: use pytest after tooling is configured; mock external APIs and FFmpeg boundaries unless a test explicitly targets integration behavior.

## JavaScript / TypeScript

- Formatter: Not used in this repo.
- Linter: Not used in this repo.
- Module / import conventions: Not used in this repo.
- Types / strictness rules: Not used in this repo.
- Frontend / build conventions: Not used in this repo.
- JS/TS-specific test rules: Not used in this repo.

## Go

- Formatter: Not used in this repo.
- Linter: Not used in this repo.
- Package layout rules: Not used in this repo.
- Error handling conventions: Not used in this repo.
- Go-specific test rules: Not used in this repo.

## SQL

- Migration conventions: Alembic migrations after database scaffolding; never change schema without a migration once migrations exist.
- Query style / naming rules: snake_case table and column names; use clear foreign keys such as `job_id`; avoid SQL string concatenation.
- DDL / DML safety rules: use transactions, parameterized queries, and scoped `WHERE` clauses for writes.

## Shell / CLI

- Shell dialect: Bash for local helper scripts after scripts are introduced.
- Formatting / linting: ShellCheck preferred after shell scripts are introduced.
- Script safety rules: quote paths, fail clearly, avoid destructive defaults, never echo secrets.

## Tests and fixtures

- Test frameworks: pytest after scaffolding.
- Fixture / mock conventions: fixtures should use small representative quiz payloads; external OpenAI, Telegram, YouTube, Quiz Bank, and FFmpeg calls must be mocked unless running explicit integration tests.
- Required test suites before close-out: run the narrowest relevant checks available in the repo; if no test/lint commands exist yet, document that in the final report.

## Framework or repo-specific exceptions

- Generated media files and render artifacts may exceed normal size expectations but should live only in approved asset directories once storage paths are defined.
