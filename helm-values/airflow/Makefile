NAMESPACE ?= data-platform
HELM_RELEASE ?= airflow

.PHONY: \
	install uninstall upgrade status port-forward help

help:
	@echo "Makefile commands for Airflow Helm Chart:"
	@echo "  make install         - Install Airflow using airflow-values.yaml"
	@echo "  make uninstall       - Uninstall Airflow"
	@echo "  make upgrade         - Apply updates from airflow-values.yaml"
	@echo "  make status          - Check Airflow pods"
	@echo "  make port-forward    - Forward local 8080 to Airflow Webserver"

install:
	@set -e; \
	printf '\033[1;33mInstalling Apache Airflow via Helm...\033[0m\n'; \
	helm repo add apache-airflow https://airflow.apache.org || true; \
	helm repo update; \
	helm upgrade --install $(HELM_RELEASE) apache-airflow/airflow \
		--namespace $(NAMESPACE) --create-namespace \
		-f airflow-values.yaml; \
	printf '\033[1;32mAirflow installed.\033[0m\n'

uninstall:
	@set -e; \
	printf '\033[1;31mUninstalling Airflow...\033[0m\n'; \
	helm uninstall $(HELM_RELEASE) -n $(NAMESPACE) || true; \
	printf '\033[1;32mAirflow uninstalled.\033[0m\n'

upgrade: install

status:
	@kubectl get pods -l release=$(HELM_RELEASE) -n $(NAMESPACE) -w

port-forward:
	@kubectl port-forward svc/$(HELM_RELEASE)-webserver 8080:8080 -n $(NAMESPACE)
