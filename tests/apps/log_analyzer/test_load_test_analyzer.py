"""Tests for deterministic load-test artifact analysis."""

import json

from apps.log_analyzer.load_test import analyze_load_test
from apps.log_analyzer.load_test import render_markdown


def test_analyze_all_artifacts(tmp_path):
    """Correlate structured results with resource and failure evidence."""
    raw_results = tmp_path / "raw_results.json"
    raw_results.write_text(
        json.dumps(
            {
                "metadata": {"agent": "agent_network_designer", "concurrency": 50},
                "requests": [
                    {"request_id": "request-1", "success": True, "duration_seconds": 2.5},
                    {"request_id": "request-2", "success": False, "duration_seconds": 10},
                ],
            }
        ),
        encoding="utf-8",
    )
    load_log = tmp_path / "load_test.log"
    load_log.write_text("RSS: 1024 MB threads: 781 executor reuse: 0%\n", encoding="utf-8")
    debug_log = tmp_path / "debug.log"
    debug_log.write_text("request_id=request-2 idle timeout after 600 sec\n", encoding="utf-8")
    server_log = tmp_path / "server.log"
    server_log.write_text("ERROR request_id=request-2 StreamClosedError\nRSS: 1.5 GB\n", encoding="utf-8")

    analysis = analyze_load_test(raw_results, load_log, debug_log, server_log)

    assert analysis["request_summary"]["total"] == 2
    assert analysis["request_summary"]["successful"] == 1
    assert analysis["disconnections"] == {"count": 1, "request_ids": ["request-2"]}
    assert analysis["resources"]["peak_rss_mb"] == 1536
    assert analysis["resources"]["peak_threads"] == 781
    assert analysis["resources"]["estimated_pod_memory_mb"] == 1920
    assert analysis["executor_pool"]["minimum_reuse_percent"] == 0
    assert [finding["severity"] for finding in analysis["findings"]] == ["high", "medium"]
    assert "HIGH" in render_markdown(analysis)


def test_missing_and_malformed_inputs_are_warnings(tmp_path):
    """Unavailable artifacts degrade gracefully without hiding parser failures."""
    malformed = tmp_path / "raw_results.json"
    malformed.write_text("{not json", encoding="utf-8")

    analysis = analyze_load_test(raw_results=malformed, server_log=tmp_path / "missing.log")

    assert analysis["request_summary"]["total"] == 0
    assert len(analysis["parse_warnings"]) == 2


def test_unknown_json_shape_is_forward_compatible(tmp_path):
    """Unknown structured output remains valid and produces an empty summary."""
    raw_results = tmp_path / "raw_results.json"
    raw_results.write_text('{"future": {"metric": 1}}', encoding="utf-8")

    analysis = analyze_load_test(raw_results=raw_results)

    assert analysis["request_summary"]["total"] == 0
    assert analysis["parse_warnings"] == []
