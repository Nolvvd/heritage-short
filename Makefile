PY ?= python3

.PHONY: validate narration radio keyframes music shots film clean-cache

validate:
	$(PY) -m pipeline.validate

narration: validate
	$(PY) -m pipeline.narration

radio: narration
	$(PY) -m pipeline.radio_cut

# Later stages are added as they are built:
# keyframes: narration -> pipeline.keyframes (Cloudflare Workers AI)
# music: Kaggle notebook (ACE-Step 1.5), outputs synced to outputs/music/
# shots: Kaggle notebook (Wan 2.2) + pipeline.kenburns for the rest
# film: pipeline.assemble -> outputs/final/film_9x16.mp4 and film_16x9.mp4
film: radio
