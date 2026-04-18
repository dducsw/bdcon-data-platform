NAMESPACE ?= data-platform
HELM_RELEASE ?= trino

.PHONY: \
	install uninstall upgrade status help

help:
	@echo "Makefile commands for Trino Helm Chart:"
	@echo "  make install         - Install Trino using trino-values.yaml"
	@echo "  make uninstall       - Uninstall Trino"
	@echo "  make upgrade         - Apply updates from trino-values.yaml"
	@echo "  make status          - Check Trino pods"

install:
	@set -e; \
	printf '\033[1;33mInstalling Trino via Helm...\033[0m\n'; \
	helm repo add trino https://trinodb.github.io/charts || true; \
	helm repo update; \
	helm upgrade --install $(HELM_RELEASE) trino/trino \
		--namespace $(NAMESPACE) --create-namespace \
		-f trino-values.yaml; \
	printf '\033[1;32mTrino installed.\033[0m\n'

uninstall:
	@set -e; \
	printf '\033[1;31mUninstalling Trino...\033[0m\n'; \
	helm uninstall $(HELM_RELEASE) -n $(NAMESPACE) || true; \
	printf '\033[1;32mTrino uninstalled.\033[0m\n'

upgrade: install

status:
	@kubectl get pods -l app=trino -n $(NAMESPACE) -w
