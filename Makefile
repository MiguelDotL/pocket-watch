PYTHON ?= python3

.PHONY: lint typecheck test privacy-check security-check check-all release

lint:
	ruff check scripts/ hooks/

typecheck:
	mypy scripts/

test:
	pytest tests/

privacy-check:
	@echo "Running privacy (tell-word) grep..."
	@if grep -rn -iE "(personal|pseudonym|anonym|scrub|redact|<user>|<TBD>|<placeholder>)" \
		--include="*.md" --include="*.json" --include="*.yml" --include="*.yaml" \
		--include="*.py" . 2>/dev/null \
		| grep -v __pycache__ \
		| grep -v ".build-report.md" \
		| grep -v "./.venv/" \
		| grep -v "./CODE_OF_CONDUCT.md"; then \
		echo "FAIL: tell-words found above"; exit 1; \
	else \
		echo "PASS: no tell-words found"; \
	fi

security-check:
	# -ll: only report medium+ severity. Low-severity hits in pocket-watch are
	# intentional patterns (subprocess for tz detection, try/except/pass for
	# hook fail-soft) per design.
	bandit -r scripts/ hooks/ -ll

check-all: lint typecheck test privacy-check security-check
	@echo "All gates passed."

release:
ifndef VERSION
	$(error VERSION is required: make release VERSION=X.Y.Z)
endif
	@echo "would tag v$(VERSION) (stubbed — run check-all first, then: git tag v$(VERSION) && git push --tags)"
