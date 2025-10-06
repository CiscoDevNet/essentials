# Makefile
# description: Build, lint, and run tasks for the essentials project
# author: Matt Norris <matnorri@cisco.com>

.PHONY: help lint-javascript lint-js install-javascript install-js

# Default target - show help
help:
	@echo "Available targets:"
	@echo "  lint-javascript (lint-js)    - Lint JavaScript packages"
	@echo "  install-javascript (install-js) - Install JavaScript dependencies"
	@echo "  help                          - Show this help message"

# Lint JavaScript packages
lint-javascript: lint-js
lint-js:
	@echo "Linting JavaScript packages..."
	@cd packages/javascript && npm run lint

# Install JavaScript dependencies
install-javascript: install-js
install-js:
	@echo "Installing JavaScript dependencies..."
	@cd packages/javascript && npm install
