.PHONY: all install streamlit-run sync update clean lint test serve
#################################################################################
# GLOBALS                                                                       #
#################################################################################

PROJECT_DIR := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
PYTHON_INTERPRETER = python3.11
SVC_NAME = multi-agent-travel-concierge

#################################################################################
# COMMANDS                                                                      #
#################################################################################
all:
	echo $(AWS_PROFILE)

## Init poetry dependencies
init:
	pip install --upgrade pip
	pip install pipx
	pipx install poetry==1.8.2
	poetry env use python3.11
	poetry shell

## Install dependencies in pyproject.toml (poetry.lock)
install:
	poetry lock
	poetry install --sync --with dev,tests
	pipx inject poetry poetry-plugin-export
	poetry export -f requirements.txt --with dev,tests --output requirements.txt
	pre-commit install
	pre-commit run --all-files

## Install llama-index
install-llama-index:
	poetry lock --no-update
	poetry install --sync --with llama-index,dev,tests
	poetry export -f requirements.txt --with llama-index,dev,tests --output requirements-llama-index.txt
	pre-commit install
	pre-commit run --all-files


## Install langgraphTo
install-langgraph:
	poetry lock --no-update
	poetry install --sync --with langgraph,dev,tests
	poetry export -f requirements.txt --with langgraph,dev,tests --output requirements-langgraph.txt
	pre-commit install
	pre-commit run --all-files

## Install crewai
install-crewai:
	poetry lock --no-update
	poetry install --sync --with crewai,dev,tests
	poetry export -f requirements.txt --with crewai,dev,tests --output requirements-crewai.txt
	pre-commit install
	pre-commit run --all-files


## Install autogen
install-autogen:
	poetry lock --no-update
	poetry install --sync --with autogen,dev,tests
	poetry export -f requirements.txt --with autogen,dev,tests --output requirements-autogen.txt
	pre-commit install
	pre-commit run --all-files


## Install ci dependencies in pyproject.toml (poetry.lock)
## TODO: @charlene; For now, we can use --no-cache-dir; but in future, can use Github runners dep caching to only rebuild when requirements*.txt changes etc
install-ci:
	pip install --no-cache-dir --upgrade pip
	pip install --no-cache-dir -r requirements.txt
	pip install --no-cache-dir -e .

## Run in streamlit
streamlit-run:
	streamlit run frontend/app.py

## Sync dependencies in .venv with poetry.lock
sync:
	poetry lock
	poetry lock --no-update
	poetry install --sync
	poetry export -f requirements.txt --with data,train,dev,tests --output requirements-train.txt
	poetry export -f requirements.txt --with serve --output requirements-serve.txt
	poetry export -f requirements.txt --with serve,tests --output requirements-ci.txt

## Delete all compiled Python files
clean:
	find . -type f -name "*.DS_Store" -ls -delete
	find . -type f -name "*.py[co]" -delete
	find . -type f -name "*.log" -delete
	find . -type f -name "*.logs" -delete
	find . -type f -name "*.coverage*" -delete
	find . -type f -name "*.temp" -delete
	find . -type d -name "*.coverage" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name "*.coverage" -exec rm -rf {} +
	find . -type d -name "*.eggs" -exec rm -rf {} +
	find . -type d -name "*.pytest_cache" -exec rm -rf {} +
	find . -type d -name "*.mypy_cache" -exec rm -rf {} +
	find . | grep -E ".ipynb_checkpoints" | xargs rm -rf
	find . -type d -empty -delete

## Lint
lint:
	ruff format .
	ruff check --fix
	# nbqa ruff notebooks
	# nbqa ruff notebooks --fix
	pre-commit run --all-files

## Clean logs
clean-logs:
	rm -rf *logs/**

## Run tests
test:
	pytest -svv

# ## Train the model
# train:
# 	python src/train.py

## Build local
build:
	python serve/build_context.py
	docker build -f serve/Dockerfile -t $(SVC_NAME) .

## Serve the model
serve:
	python src/serve.py

#################################################################################
# Self Documenting Commands                                                     #
#################################################################################

.DEFAULT_GOAL := help

.PHONY: help
help:
	@echo "$$(tput bold)Available rules:$$(tput sgr0)"
	@echo
	@sed -n -e "/^## / { \
		h; \
		s/.*//; \
		:doc" \
		-e "H; \
		n; \
		s/^## //; \
		t doc" \
		-e "s/:.*//; \
		G; \
		s/\\n## /---/; \
		s/\\n/ /g; \
		p; \
	}" ${MAKEFILE_LIST} \
	| LC_ALL='C' sort --ignore-case \
	| awk -F '---' \
		-v ncol=$$(tput cols) \
		-v indent=19 \
		-v col_on="$$(tput setaf 6)" \
		-v col_off="$$(tput sgr0)" \
	'{ \
		printf "%s%*s%s ", col_on, -indent, $$1, col_off; \
		n = split($$2, words, " "); \
		line_length = ncol - indent; \
		for (i = 1; i <= n; i++) { \
			line_length -= length(words[i]) + 1; \
			if (line_length <= 0) { \
				line_length = ncol - indent - length(words[i]) - 1; \
				printf "\n%*s ", -indent, " "; \
			} \
			printf "%s ", words[i]; \
		} \
		printf "\n"; \
	}' \
	| more $(shell test $(shell uname) = Darwin && echo '--no-init --raw-control-chars')
