"""Parse load-test artifacts into a compact, deterministic analysis."""

import json
import re
from collections import Counter
from pathlib import Path
from statistics import mean

STREAM_CLOSED_RE = re.compile(r"StreamClosedError|stream (?:was )?closed", re.IGNORECASE)
TIMEOUT_RE = re.compile(r"idle[ _-]?timeout|timed? out|timeout", re.IGNORECASE)
ERROR_RE = re.compile(r"\b(?:ERROR|CRITICAL|FATAL|Traceback)\b")
RSS_RE = re.compile(r"(?:RSS|resident(?: memory)?)\D{0,20}(\d+(?:\.\d+)?)\s*(GB|MB|MiB)", re.IGNORECASE)
THREAD_RE = re.compile(r"threads?\D{0,20}(\d+)", re.IGNORECASE)
FD_RE = re.compile(r"(?:file descriptors?|FDs?)\D{0,20}(\d+)", re.IGNORECASE)
REUSE_RE = re.compile(r"reuse(?: percent| rate|%)?\D{0,20}(\d+(?:\.\d+)?)\s*%", re.IGNORECASE)
DURATION_RE = re.compile(r"(?:duration|elapsed|latency)\D{0,20}(\d+(?:\.\d+)?)\s*(ms|s|sec)", re.IGNORECASE)
REQUEST_ID_RE = re.compile(r"(?:request[_ -]?id|request)[=: ]+([\w.-]+)", re.IGNORECASE)


def _empty_analysis(inputs):
    return {
        "schema_version": 1,
        "inputs": inputs,
        "run_metadata": {},
        "request_summary": {"total": 0, "successful": 0, "failed": 0, "durations_seconds": []},
        "disconnections": {"count": 0, "request_ids": []},
        "executor_pool": {"reuse_percent_samples": []},
        "resources": {"rss_mb_samples": [], "thread_samples": [], "fd_samples": []},
        "server_errors": {},
        "evidence": [],
        "parse_warnings": [],
        "findings": [],
        "recommendations": [],
    }


def _number(value):
    return float(value) if value is not None else None


def _first(data, *keys):
    for key in keys:
        if isinstance(data, dict) and data.get(key) is not None:
            return data[key]
    return None


def _walk_requests(data):
    """Yield likely request result dictionaries from compatible JSON layouts."""
    if isinstance(data, dict):
        for key in ("requests", "results", "raw_results"):
            value = data.get(key)
            if isinstance(value, list):
                yield from (item for item in value if isinstance(item, dict))
                return
        for value in data.values():
            if isinstance(value, (dict, list)):
                yield from _walk_requests(value)
    elif isinstance(data, list):
        yield from (item for item in data if isinstance(item, dict))


def _parse_raw_results(path, analysis):
    try:
        with path.open(encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, json.JSONDecodeError) as exc:
        analysis["parse_warnings"].append(f"Could not parse {path}: {exc}")
        return

    if isinstance(data, dict):
        metadata = _first(data, "metadata", "run_metadata", "config", "configuration")
        if isinstance(metadata, dict):
            analysis["run_metadata"].update(metadata)

    requests = list(_walk_requests(data))
    for request in requests:
        status = str(_first(request, "status", "result", "outcome") or "").lower()
        success = _first(request, "success", "successful", "ok")
        if success is None:
            success = status in {"success", "successful", "passed", "created", "ok", "200"}
        analysis["request_summary"]["successful" if success else "failed"] += 1
        duration = _number(_first(request, "duration_seconds", "elapsed_seconds", "latency_seconds", "duration"))
        if duration is not None:
            analysis["request_summary"]["durations_seconds"].append(duration)
    analysis["request_summary"]["total"] = len(requests)


def _add_evidence(analysis, source, line_number, category, text):
    if sum(1 for item in analysis["evidence"] if item["category"] == category) >= 20:
        return
    analysis["evidence"].append(
        {"source": source, "line": line_number, "category": category, "text": text.strip()[:500]}
    )


def _parse_log(path, analysis):
    errors = Counter(analysis["server_errors"])
    try:
        with path.open(encoding="utf-8", errors="replace") as stream:
            for line_number, line in enumerate(stream, 1):
                if STREAM_CLOSED_RE.search(line):
                    analysis["disconnections"]["count"] += 1
                    request_id = REQUEST_ID_RE.search(line)
                    if request_id:
                        analysis["disconnections"]["request_ids"].append(request_id.group(1))
                    _add_evidence(analysis, path.name, line_number, "disconnection", line)
                if TIMEOUT_RE.search(line):
                    _add_evidence(analysis, path.name, line_number, "timeout", line)
                if ERROR_RE.search(line):
                    error_name = re.search(r"([A-Za-z]+(?:Error|Exception))", line)
                    errors[error_name.group(1) if error_name else "error"] += 1
                    _add_evidence(analysis, path.name, line_number, "error", line)
                for pattern, key in ((RSS_RE, "rss_mb_samples"), (THREAD_RE, "thread_samples"), (FD_RE, "fd_samples")):
                    match = pattern.search(line)
                    if match:
                        value = float(match.group(1))
                        if pattern is RSS_RE and match.group(2).lower() == "gb":
                            value *= 1024
                        analysis["resources"][key].append(value)
                reuse = REUSE_RE.search(line)
                if reuse:
                    analysis["executor_pool"]["reuse_percent_samples"].append(float(reuse.group(1)))
                duration = DURATION_RE.search(line)
                if duration:
                    value = float(duration.group(1))
                    if duration.group(2).lower() == "ms":
                        value /= 1000
                    analysis["request_summary"]["durations_seconds"].append(value)
    except OSError as exc:
        analysis["parse_warnings"].append(f"Could not read {path}: {exc}")
    analysis["server_errors"] = dict(errors)


def _summarize(analysis):
    resources = analysis["resources"]
    requests = analysis["request_summary"]
    durations = requests.pop("durations_seconds")
    requests["average_duration_seconds"] = round(mean(durations), 3) if durations else None
    requests["max_duration_seconds"] = round(max(durations), 3) if durations else None
    resources["peak_rss_mb"] = max(resources.pop("rss_mb_samples"), default=None)
    resources["peak_threads"] = max(resources.pop("thread_samples"), default=None)
    resources["peak_fds"] = max(resources.pop("fd_samples"), default=None)
    reuse = analysis["executor_pool"].pop("reuse_percent_samples")
    analysis["executor_pool"]["minimum_reuse_percent"] = min(reuse, default=None)
    analysis["disconnections"]["request_ids"] = sorted(set(analysis["disconnections"]["request_ids"]))

    timeout_evidence = any(item["category"] == "timeout" for item in analysis["evidence"])
    if analysis["disconnections"]["count"]:
        confidence = "high" if timeout_evidence else "medium"
        analysis["findings"].append(
            {"severity": "high", "confidence": confidence, "title": "Client disconnections detected"}
        )
        analysis["recommendations"].append("Review timeout evidence and rerun with an increased idle timeout.")
    reuse_min = analysis["executor_pool"]["minimum_reuse_percent"]
    if reuse_min is not None and reuse_min < 25:
        analysis["findings"].append(
            {"severity": "medium", "confidence": "high", "title": "Low executor-pool reuse observed"}
        )
        analysis["recommendations"].append("Investigate executor return contention and cap retained pool size.")
    peak_rss = resources["peak_rss_mb"]
    if peak_rss is not None:
        resources["estimated_pod_memory_mb"] = int(peak_rss * 1.25 + 0.5)
        analysis["recommendations"].append(
            "Treat pod memory as observed peak RSS plus a 25% safety margin, not a generalized capacity model."
        )
    if not analysis["inputs"]:
        analysis["parse_warnings"].append("No input artifacts were supplied.")


def analyze_load_test(raw_results=None, load_test_log=None, debug_log=None, server_log=None):
    """Return a JSON-serializable load-test analysis for the supplied artifacts."""
    supplied = {
        name: str(path)
        for name, path in {
            "raw_results": raw_results,
            "load_test_log": load_test_log,
            "debug_log": debug_log,
            "server_log": server_log,
        }.items()
        if path
    }
    analysis = _empty_analysis(supplied)
    if raw_results:
        _parse_raw_results(Path(raw_results), analysis)
    for path in (load_test_log, debug_log, server_log):
        if path:
            _parse_log(Path(path), analysis)
    _summarize(analysis)
    return analysis
