PY ?= python

.PHONY: validate narration radio refs keyframes draft film test

validate:
	$(PY) -m pipeline.validate

narration: validate
	$(PY) -m pipeline.narration

radio: narration
	$(PY) -m pipeline.radio_cut

refs: validate
	$(PY) -m pipeline.keyframes --refs-only

keyframes: validate
	$(PY) -m pipeline.keyframes

draft:
	$(PY) -m pipeline.run --draft

film:
	$(PY) -m pipeline.run

test:
	$(PY) -m unittest discover tests
