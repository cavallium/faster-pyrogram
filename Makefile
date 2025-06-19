VENV := venv
PYTHON := $(VENV)/bin/python
TAG = v$(shell grep -E '__version__ = ".*"' pyrogram/__init__.py | cut -d\" -f2)

RM := rm -rf

.PHONY: venv clean-build clean-api clean-docs clean api docs build tag dtag

venv:
	python3 -m venv $(VENV)
	$(PYTHON) -m pip install -U pip wheel setuptools
	$(PYTHON) -m pip install -U -e .[docs]
	@echo "Created venv with $$($(PYTHON) --version)"

clean-venv:
	$(RM) $(VENV)
	@echo "Cleaned venv directory"

clean-build:
	$(RM) *.egg-info build dist
	@echo "Cleaned build directory"

clean-api:
	$(RM) pyrogram/errors/exceptions pyrogram/raw/all.py pyrogram/raw/base pyrogram/raw/functions pyrogram/raw/types
	@echo "Cleaned api directory"

clean-docs:
	$(RM) docs/build docs/source/api/bound-methods docs/source/api/methods docs/source/api/types docs/source/api/enums docs/source/telegram
	@echo "Cleaned docs directory"

clean: clean-venv clean-build clean-api clean-docs
	@echo "Cleaned all directories"

api:
	cd compiler/api && ../../$(PYTHON) compiler.py
	cd compiler/errors && ../../$(PYTHON) compiler.py

docs:
	cd compiler/docs && ../../$(PYTHON) compiler.py
	$(VENV)/bin/sphinx-build -b dirhtml "docs/source" "docs/build/html" -j auto
	cd docs/build/html && zip -r ../docs.zip ./

build:
	hatch build

tag:
	git tag $(TAG)
	git push origin $(TAG)

dtag:
	git tag -d $(TAG)
	git push origin -d $(TAG)
