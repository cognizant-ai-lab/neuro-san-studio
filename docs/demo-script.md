# Fraud War Room — 3–5 minute demo script

## 0:00 — Set the scene

Open the command center and say: “This is a synthetic NA BFS environment. The differentiator is not another fraud score; it is a closed-loop organization that keeps asking what the attacker will do next.”

Select `CASE-0001`. Point out the open alert, CRITICAL risk, and loss at risk. The alert is only the starting signal.

## 0:40 — Investigate and understand

Walk left to right:

- Transaction Analyst calculates the amount/velocity/novelty/sequence signals.
- Customer Analyst keeps the legitimate explanation alive against the customer baseline.
- Entity / Graph Analyst finds the beneficiary and related accounts in the campaign component.
- Timeline / Process Analyst reconstructs access → setup → probe → extraction → movement.
- Hypothesis Generator preserves takeover, authorized unusual activity, and coordinated campaign as competing explanations.

Open the Evidence tab and distinguish supporting, counter-, and missing evidence. Emphasize that graph traversal and arithmetic are deterministic coded tools, not LLM guesses.

## 1:45 — Challenge the conclusion

Show the independent model assessment strip in the Decision Passport. Explain that high-risk cases collect multiple opinions. If the confidence spread exceeds the configured threshold, disagreement triggers more evidence and challenger review; the opinions are not silently averaged.

Point to the Challenger activity: “Unusual behavior is not proof of unauthorized intent, so the system must retain the authorized explanation while it escalates.”

## 2:20 — Attack the defense

Show the Defense Comparison table. Explain that each candidate is evaluated across the synthetic population for fraud prevented, loss prevented, false positives, friction, workload, cost, latency, and attack success probability.

Point out the adversarial rounds: the attacker splits payments, waits, rotates devices, or hops beneficiaries; the defender adds a sequence or relationship predicate; the simulator recalculates the outcome. The loop has an explicit maximum iteration and convergence condition.

## 3:10 — Govern and approve

Open the Decision Passport. Explain that it contains concise evidence references, reason codes, model disagreement, the selected control, simulation results, governance checks, and audit events—never chain-of-thought.

Click “Approve & enter shadow.” Say: “Approval does not activate a production control. Governance moves it to SHADOW only.”

## 3:40 — Observe, learn, repeat

Click “Introduce attacker variation.” The system introduces the next synthetic bypass and either shows it contained or proposes a revised shadow control. Point to the learning record: predicted versus observed outcome, error, failure mode, and successful defense.

Close with: “That is the difference between a detector and a defense organization: it investigates, stress-tests itself, simulates the trade-offs, governs the action, and learns from what happens next.”
