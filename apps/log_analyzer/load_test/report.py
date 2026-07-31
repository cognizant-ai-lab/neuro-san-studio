"""Render normalized load-test analysis as Markdown."""


def _value(value, suffix=""):
    return "not observed" if value is None else f"{value}{suffix}"


def render_markdown(analysis):
    """Render a concise evidence-backed Markdown report."""
    requests = analysis["request_summary"]
    resources = analysis["resources"]
    pool = analysis["executor_pool"]
    disconnections = analysis["disconnections"]
    lines = [
        "# Load Test Analysis",
        "",
        "## Summary",
        "",
        f"- Requests: {requests['total']} total, {requests['successful']} successful, {requests['failed']} failed",
        f"- Client disconnections: {disconnections['count']}",
        f"- Peak RSS: {_value(resources['peak_rss_mb'], ' MB')}",
        f"- Peak threads: {_value(resources['peak_threads'])}",
        f"- Minimum executor reuse: {_value(pool['minimum_reuse_percent'], '%')}",
        "",
        "## Findings",
        "",
    ]
    if analysis["findings"]:
        for finding in analysis["findings"]:
            lines.append(
                f"- **{finding['severity'].upper()}** ({finding['confidence']} confidence): {finding['title']}"
            )
    else:
        lines.append("- No configured issue signatures were found.")
    lines.extend(["", "## Recommendations", ""])
    lines.extend(f"- {item}" for item in analysis["recommendations"] or ["No automatic recommendations."])
    lines.extend(["", "## Evidence", ""])
    for item in analysis["evidence"][:30]:
        lines.append(f"- `{item['source']}:{item['line']}` [{item['category']}] {item['text']}")
    if not analysis["evidence"]:
        lines.append("- No evidence lines captured.")
    if analysis["parse_warnings"]:
        lines.extend(["", "## Parse warnings", ""])
        lines.extend(f"- {warning}" for warning in analysis["parse_warnings"])
    return "\n".join(lines) + "\n"
