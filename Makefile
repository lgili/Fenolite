# Private residue lists (gitignored) are picked up automatically when present.
ifneq (,$(wildcard private/residue-tokens.txt))
export FENOLITE_RESIDUE_TOKENS_FILE ?= private/residue-tokens.txt
endif
ifneq (,$(wildcard private/residue-blobs.sha256))
export FENOLITE_RESIDUE_BLOBS_FILE ?= private/residue-blobs.sha256
endif

# Tests run on several pytest-xdist workers (capability ci-baseline, "Parallel test runs").
# `auto` is one worker per CPU, capped because kicad-cli starts threads of its own.
# Override per call, for example: make check PYTEST_MAX_WORKERS=4   (PYTEST_WORKERS=0 is serial)
PYTEST_WORKERS ?= auto
PYTEST_MAX_WORKERS ?= 8
PYTEST_PARALLEL ?= -n $(PYTEST_WORKERS) --maxprocesses $(PYTEST_MAX_WORKERS) --dist loadfile

.PHONY: check check-fast lint format types test test-fast residue hooks agent-eval

# The gate before a merge: every check and every test.
check: lint format types residue test

# While iterating: the same checks, and the tests that need no kicad-cli, corpus or KiCad libraries.
check-fast: lint format types residue test-fast

# lint also says whether the generated pages of the agent guide are current (the tool writes them).
lint:
	uv run ruff check .
	uv run python tools/gen_agent_guide.py --check

format:
	uv run ruff format --check .

types:
	uv run pyright src

test:
	uv run pytest -q $(PYTEST_PARALLEL)

test-fast:
	uv run pytest tests/unit tests/residue tests/consistency -q $(PYTEST_PARALLEL) -m "not needs_kicad and not needs_corpus and not needs_libs"

residue:
	uv run python tools/residue/scan.py

hooks:
	ln -sf ../../tools/hooks/pre-commit .git/hooks/pre-commit
	@echo "pre-commit hook installed"

# The yardstick board through the loop of its stage, on a local library cache and kicad-cli 10. Not a
# part of `check`: it takes minutes. `make yardstick YARDSTICK_ARGS=--skip-heavy` leaves the two heavy
# corpus boards out (tools/README.md, "The yardstick").
.PHONY: yardstick
YARDSTICK_OUT ?= build/yardstick
YARDSTICK_ARGS ?=
yardstick:
	rm -rf $(YARDSTICK_OUT)
	FENOLITE_LIBS_CACHE=$${FENOLITE_LIBS_CACHE:-$$HOME/.cache/fenolite/libs} uv run python tools/yardstick.py run --out $(YARDSTICK_OUT) --record $(YARDSTICK_OUT)/record.json $(YARDSTICK_ARGS)

# One task of the agent evaluation with one runner (tools/README.md, "Agent evaluation").
# RUNNER=replay plays the reference solution and starts no agent. Any other runner starts a real
# agent, which costs money: pass ARGS=--yes yourself, never from CI.
TASK ?= led-indicator
RUNNER ?= replay
agent-eval:
	uv run python tools/agent_eval/run.py --task $(TASK) --runner $(RUNNER) $(ARGS)
