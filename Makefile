# Makefile
# description: Build, lint, and run tasks for the essentials project
# author: Matt Norris <matnorri@cisco.com>

.PHONY: help install-skills lint-javascript lint-js install-javascript install-js test-javascript test-js

# Default target - show help
help:
	@echo "Available targets:"
	@echo "  install-skills                - Install skills, rules, and MCP servers declared in apm.yml"
	@echo "  lint-javascript (lint-js)    - Lint JavaScript packages"
	@echo "  test-javascript (test-js)    - Test JavaScript packages"
	@echo "  install-javascript (install-js) - Install JavaScript dependencies"
	@echo "  help                          - Show this help message"

# Install skills into .agents/skills/, rules into .cursor/rules/, and MCP servers
# into .cursor/mcp.json: APM deploys everything declared in apm.yml. Sources stay
# in skills/ and instructions/; commit the installed copies and apm.lock.yaml.
install-skills:
	apm install
	./tools/shell/apm-lock-check-ignored/apm-lock-check-ignored.sh

# Lint JavaScript packages
lint-javascript: lint-js
lint-js:
	@echo "Linting JavaScript packages..."
	@cd packages/javascript && npm run lint

# Test JavaScript packages
test-javascript: test-js
test-js:
	@echo "Testing JavaScript packages..."
	@cd packages/javascript && npm test

# Install JavaScript dependencies
install-javascript: install-js
install-js:
	@echo "Installing JavaScript dependencies..."
	@cd packages/javascript && npm install
