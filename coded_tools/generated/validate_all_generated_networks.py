"""
Aggregate validator for all active generated networks.
Runs per-network validation and reports where any generated network stops.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from json import JSONDecoder


ROOT = Path(__file__).resolve().parent


def run_json_command(cmd: list[str]) -> dict:
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    stdout = result.stdout.strip()
    decoder = JSONDecoder()
    for idx, char in enumerate(stdout):
        if char != "{":
            continue
        try:
            payload, end = decoder.raw_decode(stdout[idx:])
            if idx + end == len(stdout):
                return payload
        except json.JSONDecodeError:
            continue
    raise ValueError(f"No JSON payload found in command output: {stdout[:500]}")


def main() -> None:
    started_at = datetime.now().isoformat()

    summary = {
        "started_at": started_at,
        "generated_networks": [],
    }

    networks = [
        {
            "name": "generated/underwriting_analytics_ure_system",
            "validator": ROOT / "underwriting_analytics_ure_system" / "validate_network.py",
        },
        {
            "name": "generated/rule_based_ai_underwriting_system",
            "validator": ROOT / "rule_based_ai_underwriting_system" / "validate_network.py",
        },
    ]

    for network in networks:
        report = run_json_command(["python3", str(network["validator"])])
        summary["generated_networks"].append(
            {
                "name": network["name"],
                "network_running": report.get("network_running"),
                "stop_after_step": report.get("stop_after_step"),
                "validations": report.get("validations", []),
            }
        )

    summary["all_running"] = all(item["network_running"] for item in summary["generated_networks"])
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
