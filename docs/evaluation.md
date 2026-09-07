# Fraud War Room evaluation

The benchmark is generated locally with `seed=17` and defaults to 600 cases. It includes fraud, legitimate high-value activity, travel, false positives, account takeover, beneficiary fraud, mule networks, coordinated payment fraud, card anomalies, velocity attacks, and device anomalies. Each case has hidden labels that are used only by the evaluator and simulator.

Run:

```bash
python -c "from coded_tools.fraud_defense.benchmark import run_benchmark; run_benchmark(output_path='artifacts/fraud_benchmark.json')"
```

The output compares three modes:

1. `baseline_rules_human_workflow`: a score threshold and ordinary review path.
2. `agentic_investigation`: risk signals plus graph/timeline context, without attacker/defender simulation.
3. `full_adversarial_defense_engine`: adaptive signal threshold, campaign context, control simulation, and structured governance.

Reported fields are computed from generated labels or explicit deterministic proxy formulas: recall, precision, false-positive rate, investigation time, evidence coverage, campaign discovery, attack-path discovery, defense effectiveness, false-positive impact, customer-friction proxy, workload, adaptation time, disagreement rate, escalation rate, and simulation-to-real outcome error.

The time, friction, workload, and adaptation fields are prototype cost proxies—not observed bank production measurements. No result should be presented as a production benchmark, regulatory certification, or client outcome.
