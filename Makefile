# Private residue lists (gitignored) are picked up automatically when present.
ifneq (,$(wildcard private/residue-tokens.txt))
export FENOLITE_RESIDUE_TOKENS_FILE ?= private/residue-tokens.txt
endif
ifneq (,$(wildcard private/residue-blobs.sha256))
export FENOLITE_RESIDUE_BLOBS_FILE ?= private/residue-blobs.sha256
endif

.PHONY: check lint format types test residue hooks

check: lint format types test

lint:
	uv run ruff check .

format:
	uv run ruff format --check .

types:
	uv run pyright src

test:
	uv run pytest -q

residue:
	uv run python tools/residue/scan.py

hooks:
	ln -sf ../../tools/hooks/pre-commit .git/hooks/pre-commit
	@echo "pre-commit hook installed"
