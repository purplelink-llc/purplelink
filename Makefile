# Purplelink LLC — convenience targets.
# Real work lives in scripts/; this is a thin wrapper so `make deploy` does
# the right thing.

.PHONY: deploy deploy-backend deploy-dry test ping help

help:
	@echo "Targets:"
	@echo "  make deploy         — netlify deploy --prod + IndexNow ping"
	@echo "  make deploy-backend — same as 'deploy' plus modal deploy of backend/"
	@echo "  make deploy-dry     — preview what 'make deploy' would do, without executing"
	@echo "  make ping           — just ping IndexNow about today's lastmod URLs"
	@echo "  make ping-all       — ping IndexNow about every URL in the sitemap"
	@echo "  make test           — run backend pytest suite"

deploy:
	@bash scripts/deploy.sh

deploy-backend:
	@bash scripts/deploy.sh --backend

deploy-dry:
	@bash scripts/deploy.sh --dry-run

ping:
	@python3 scripts/indexnow_ping.py

ping-all:
	@python3 scripts/indexnow_ping.py --all

test:
	@cd backend && python3 -m pytest -q
