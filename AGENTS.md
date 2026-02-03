You're working on the source code for `miniwdl`, the Workflow Description Language (WDL) runner and developer toolkit.

Read `CONTRIBUTING.md` for an overview of the codebase and development workflow. In particular:
- If you're not started in a suitable virtualenv, bootstrap one under `venv/`.
- Python code should be linted with `mypy`, `ruff check --fix`, and `ruff format`.
- Testing guidelines:
    - The test suite assumes access to the Internet and dockerd (via unix socket), so make sure you have the necessary user permissions before proceeding.
    - While iterating on a task, it's usually best to run a targeted set of test cases that turns around quickly.
    - It's worth running `make qtest` before final task completion, but it takes a few minutes.
    - Reserve the full `make test` for user request or when you're sure the diff involves one of the slower unit tests or integration tests skipped by `make qtest`.

For many tasks it'll be useful to refer to the WDL 1.2 specification, which you can find under `spec/wdl-1.2/SPEC.md`. The version changelog is `spec/wdl-1.2/CHANGELOG.md`, and the older version 1.1 spec is `spec/wdl-1.1/SPEC.md`.

These development tutorials under `docs/` introduce a few common ways the codebase is used and extended.
- `trace_identifiers.md` -- basic syntax tree traversal
- `wdlviz.md` -- generating graphviz diagrams from WDL source code
- `add_functions.md `-- adding new functions to the standard library
- `assert.md` -- adding a new WDL language feature, with parsing, type-checking, and runtime execution

## Planning: WDL 1.2 task-scoped runtime info

### Goals
- Implement the WDL 1.2 "Runtime Access to Requirements, Hints, and Metadata" feature by exposing
  the implicit `task` variable at runtime.
- Minimum plausible compliance: focus on command/output usage, avoid speculative extensions.
- Provide a hook for backends to supply actual runtime values when available.

### Nuances/decisions
- `task` is available only in command and output sections (not input/postinput/runtime), to avoid
  circular evaluation and align with a conservative spec interpretation.
- `task.attempt` is currently not retry-aware because the command is not re-interpolated per retry;
  note this is intentionally left for later.
- Defaults are minimal but not empty: fall back to requested values and host limits when actuals
  are unavailable.
- `task.ext` is intentionally omitted for now.
- Model `task` as a synthetic struct instance (not a new "scoped type" system).

### Plan
- Add a synthetic struct type for `task` during typechecking (WDL 1.2+ only).
- Bind a `task` value at runtime before command interpolation and again before output evaluation.
- Add a TaskContainer hook for runtime info overrides and track the last exit code.
- Add tests for scoping and runtime values.

### Done so far
- Added `TaskContainer.last_exit_code` and `TaskContainer.task_runtime_info` hook.
- Added synthetic `task` struct type for typechecking (command/output only, WDL 1.2+).
- Injected `task` values in runtime evaluation (pre-command, pre-output), with minimal defaults.
- Added tests:
  - `tests/test_7runner.py::TestTaskRuntimeInfo` for runtime values.
  - `tests/test_1doc.py::TestTasks.test_task_scoped_info` for scoping rules.
- Ran `make pretty` and `make check`; both fail due to existing repo-wide lint issues (E501/E741),
  not from these changes.
