# Fraud War Room

Fraud War Room is the Cognizant NA BFS hackathon application in this repository: a Neuro SAN-powered Fraud Defense Autonomy Engine for synthetic banking data.

It is a closed loop, not a fraud chatbot:

`DETECT → INVESTIGATE → UNDERSTAND → ATTACK → DEFEND → SIMULATE → CHALLENGE → GOVERN → APPROVE → SHADOW → OBSERVE → LEARN`

## Run locally

From the repository root:

```bash
python -m apps.fraud_war_room --port 8090
```

Open <http://127.0.0.1:8090>. The dashboard uses seeded synthetic data and does not need a provider key. Its activity panel is explicitly a deterministic coded-tool workbench trace; it does not claim a live LLM/provider execution.

The Neuro SAN network is served by the regular Studio runner:

```bash
ns run
```

Open NSFlow and select `fraud_defense` from the network picker. The chat request should include a synthetic case ID, for example `Investigate CASE-0001`. The Neuro SAN chat path requires `GOOGLE_API_KEY` or `NVIDIA_API_KEY` in `.env`; the local dashboard and deterministic coded tools do not require a provider key. The optional multi-provider router reads the role settings in `config/fraud_defense_models.json`.

## Demo flow

1. Open `CASE-0001`, the coordinated payment-fraud campaign.
2. Review the graph, reconstructed timeline, competing hypotheses, evidence, and independent opinions.
3. Compare the three calculated controls and inspect the selected defense.
4. Approve the recommendation. The control enters `SHADOW`, never production.
5. Introduce the next attacker variation. The dashboard shows whether a bypass is detected and the revised control.
6. Open the Decision Passport for the audit artifact.

## Benchmark

```bash
python -c "from coded_tools.fraud_defense.benchmark import run_benchmark; import json; print(json.dumps(run_benchmark(output_path='artifacts/fraud_benchmark.json'), indent=2))"
```

The benchmark defaults to 600 cases and compares rules/human workflow, agentic investigation, and the full adversarial engine against hidden generated labels. Results are reproducible for a fixed seed and are not production performance claims.

## Safety boundary

The application contains no Cognizant or client data, commits no API keys, and has no production execution path. CRITICAL decisions require human approval. Controls can only be observed in the local synthetic environment.
