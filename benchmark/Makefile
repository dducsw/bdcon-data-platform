# =============================================================================
# Makefile — TPC-DS benchmark pipeline
#
# Usage:
#   make benchmark-all          run full pipeline (sequential)
#   make benchmark-spark        run only Spark job
#   make benchmark-trino        run only Trino job
#   make benchmark-report       build report from existing results
#   make benchmark-clean        delete all raw results (keep reports)
#   make benchmark-status       show job pod status
# =============================================================================
NAMESPACE      := data-platform
SPARK_JOB      := spark-benchmark-runner
TRINO_JOB      := trino-benchmark-runner
REPORT_JOB     := benchmark-report-builder
KUBECTL        := kubectl -n $(NAMESPACE)
TIMEOUT        := 7200   # seconds to wait for each job

.PHONY: benchmark-all benchmark-spark benchmark-trino benchmark-report \
        benchmark-clean benchmark-status

## Full pipeline: Spark → Trino → report (sequential to avoid resource contention)
benchmark-all: benchmark-spark benchmark-trino benchmark-report

benchmark-spark:
	@echo "=== Deleting stale Spark job (if any) ==="
	-$(KUBECTL) delete job $(SPARK_JOB) --ignore-not-found
	@echo "=== Submitting Spark benchmark job ==="
	$(KUBECTL) apply -f k8s/spark-benchmark-job.yaml
	@echo "=== Waiting for Spark job to complete ==="
	$(KUBECTL) wait job/$(SPARK_JOB) \
		--for=condition=complete \
		--timeout=$(TIMEOUT)s
	@echo "=== Spark job done ==="

benchmark-trino:
	@echo "=== Deleting stale Trino job (if any) ==="
	-$(KUBECTL) delete job $(TRINO_JOB) --ignore-not-found
	@echo "=== Submitting Trino benchmark job ==="
	$(KUBECTL) apply -f k8s/trino-benchmark-job.yaml
	@echo "=== Waiting for Trino job to complete ==="
	$(KUBECTL) wait job/$(TRINO_JOB) \
		--for=condition=complete \
		--timeout=$(TIMEOUT)s
	@echo "=== Trino job done ==="

benchmark-report:
	@echo "=== Deleting stale report job (if any) ==="
	-$(KUBECTL) delete job $(REPORT_JOB) --ignore-not-found
	@echo "=== Running report builder ==="
	$(KUBECTL) apply -f k8s/benchmark-infra.yaml
	$(KUBECTL) wait job/$(REPORT_JOB) \
		--for=condition=complete \
		--timeout=300s
	@echo "=== Fetching report ==="
	$(KUBECTL) logs job/$(REPORT_JOB)

benchmark-clean:
	@echo "=== Deleting all benchmark jobs ==="
	-$(KUBECTL) delete job $(SPARK_JOB) $(TRINO_JOB) $(REPORT_JOB) --ignore-not-found
	@echo "To wipe raw results, exec into a pod with the PVC mounted and rm -rf /benchmark/results/raw/"

benchmark-status:
	@echo "=== Jobs ==="
	$(KUBECTL) get jobs -l app=benchmark
	@echo ""
	@echo "=== Pods ==="
	$(KUBECTL) get pods -l app=benchmark -o wide