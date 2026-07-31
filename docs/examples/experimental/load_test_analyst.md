# Load Test Analyst

The **Load Test Analyst** ingests neuro-san load-test artifacts, extracts deterministic metrics and evidence, and produces
Markdown and JSON reports. It complements the existing interaction [Log Analyzer](log_analyzer.md); it does not send
hundreds of megabytes of raw logs to an LLM.

## Files

- [Application](../../../apps/log_analyzer/log_analyzer.py)
- [Agent network](../../../registries/experimental/load_test_analyst.hocon)

## Usage

All inputs are optional, but `raw_results.json` is the preferred source for request outcomes. Human-readable logs add
resource, timeout, executor-pool, and server-error evidence.

```bash
python -m apps.log_analyzer.log_analyzer load-test \
    --raw-results /path/to/raw_results.json \
    --load-test-log /path/to/load_test.log \
    --debug-log /path/to/debug.log \
    --server-log /path/to/server.log \
    --output load_test_analysis.md \
    --json-output load_test_analysis.json
```

The parser reads log files line-by-line and retains a bounded number of evidence samples per category. Missing or malformed
inputs appear under `parse_warnings`; they do not prevent analysis of the remaining files.

## Interpretation

The deterministic report includes request outcomes, duration summaries, disconnections, executor reuse, peak RSS, peak
threads, server errors, findings, recommendations, and source line evidence. A pod-memory recommendation is the observed
peak RSS plus a 25% safety margin. It is not a generalized sizing curve unless the input covers multiple concurrency stages.

To obtain an additional agent interpretation, enable `experimental/load_test_analyst.hocon` in the experimental manifest
and submit the normalized JSON report to that network. Review raw logs for secrets or sensitive request content before
sharing them; only bounded matching lines are copied into the normalized report.
