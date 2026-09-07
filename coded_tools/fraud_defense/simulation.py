"""Counterfactual control simulation and bounded attacker/defender loop."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from dataclasses import dataclass
from typing import Any
from typing import Dict
from typing import Iterable
from typing import List

from coded_tools.fraud_defense.analytics import TransactionAnalytics
from coded_tools.fraud_defense.models import SyntheticEnvironment


@dataclass
class DefenseCandidate:
    """A deployable control proposal expressed as transparent predicates."""

    control_id: str
    name: str
    action: str
    friction: str
    operational_cost: float
    conditions: List[str]
    rationale: str
    lifecycle: str = "RECOMMEND"

    def as_dict(self) -> Dict[str, Any]:
        """Return the candidate as JSON-compatible data."""
        return asdict(self)


def default_defenses() -> List[DefenseCandidate]:
    """Return distinct controls rather than repeated LLM summaries."""
    return [
        DefenseCandidate("CTRL-A", "Adaptive velocity hold", "Step up after velocity or amount anomaly", "high", 1.35, ["velocity_30m>=3", "amount_anomaly>=0.45"], "Catches rapid bursts and large deviations but may interrupt legitimate spikes."),
        DefenseCandidate("CTRL-B", "Beneficiary-device correlation", "Step up when a new beneficiary meets a new device or linked account", "low", 0.85, ["new_beneficiary&new_device", "new_beneficiary&network_link"], "Adds relationship context before applying friction."),
        DefenseCandidate("CTRL-C", "Sequence and network guard", "Hold a suspicious sequence when a probe precedes extraction or network movement", "medium", 1.05, ["test_then_transfer", "sequence_score>=0.55", "network_link>=1&new_beneficiary"], "Targets coordinated behavior while avoiding amount-only blocking."),
    ]


class DefenseSimulator:
    """Evaluate control predicates against all hidden-labeled synthetic cases."""

    def __init__(self, environment: SyntheticEnvironment, analytics: TransactionAnalytics):
        self.environment = environment
        self.analytics = analytics
        self._signals: Dict[str, Dict[str, Any]] = {}

    def signals_for_case(self, case_id: str) -> Dict[str, Any]:
        """Cache exact features used by simulations."""
        if case_id not in self._signals:
            self._signals[case_id] = self.analytics.signals(case_id)
        return self._signals[case_id]

    @staticmethod
    def triggers(control: DefenseCandidate | Dict[str, Any], signals: Dict[str, Any]) -> bool:
        """Evaluate a candidate's simple, auditable condition language."""
        candidate = control if isinstance(control, DefenseCandidate) else DefenseCandidate(**{key: control[key] for key in ("control_id", "name", "action", "friction", "operational_cost", "conditions", "rationale")}, lifecycle=control.get("lifecycle", "RECOMMEND"))
        for condition in candidate.conditions:
            clauses = condition.split("&")
            satisfied = True
            for clause in clauses:
                if ">=" in clause:
                    key, raw = clause.split(">=", 1)
                    key = {"network_link": "network_link_count"}.get(key, key)
                    satisfied = satisfied and float(signals.get(key, 0.0)) >= float(raw)
                elif clause == "new_beneficiary":
                    satisfied = satisfied and bool(signals.get("new_beneficiary"))
                elif clause == "new_device":
                    satisfied = satisfied and bool(signals.get("new_device"))
                elif clause == "network_link":
                    satisfied = satisfied and bool(signals.get("network_link_count"))
                elif clause == "test_then_transfer":
                    satisfied = satisfied and bool(signals.get("has_test_then_transfer"))
                else:
                    satisfied = False
            if satisfied:
                return True
        return False

    def evaluate(self, control: DefenseCandidate, cases: Iterable[Dict[str, Any]] | None = None, variant: str = "base") -> Dict[str, Any]:
        """Calculate fraud, friction, workload, cost, and attack success metrics."""
        selected_cases = list(self.environment.cases if cases is None else cases)
        fraud_cases = [case for case in selected_cases if case["ground_truth"]["fraud"]]
        legitimate_cases = [case for case in selected_cases if not case["ground_truth"]["fraud"]]
        prevented = 0
        loss_prevented = 0.0
        triggered = 0
        false_positive = 0
        for case in selected_cases:
            signals = self._variant(self.signals_for_case(case["case_id"]), variant)
            blocked = self.triggers(control, signals)
            if blocked:
                triggered += 1
                if case["ground_truth"]["fraud"]:
                    prevented += 1
                    loss_prevented += float(case["ground_truth"]["loss_at_risk"])
                else:
                    false_positive += 1
        total_loss = sum(float(case["ground_truth"]["loss_at_risk"]) for case in fraud_cases) or 1.0
        fraud_prevented_rate = prevented / max(1, len(fraud_cases))
        false_positive_rate = false_positive / max(1, len(legitimate_cases))
        friction_multiplier = {"low": 0.55, "medium": 1.0, "high": 1.6}[control.friction]
        friction = min(1.0, (triggered / max(1, len(selected_cases))) * friction_multiplier)
        workload = triggered / max(1, len(selected_cases))
        operational_cost = round(control.operational_cost * triggered + 0.08 * len(selected_cases), 2)
        utility = round(0.55 * (loss_prevented / total_loss) + 0.30 * fraud_prevented_rate - 0.25 * false_positive_rate - 0.08 * friction - 0.02 * operational_cost / max(1, len(selected_cases)), 4)
        return {
            "control_id": control.control_id,
            "control_name": control.name,
            "variant": variant,
            "fraud_prevented": prevented,
            "fraud_prevented_rate": round(fraud_prevented_rate, 4),
            "fraud_loss_prevented": round(loss_prevented, 2),
            "false_positives": false_positive,
            "false_positive_rate": round(false_positive_rate, 4),
            "customer_friction": round(friction, 4),
            "investigator_workload": round(workload, 4),
            "operational_cost": operational_cost,
            "legitimate_transaction_impact": round(false_positive_rate, 4),
            "latency_ms": int(38 + triggered * 0.7 + (14 if control.friction == "high" else 0)),
            "attack_success_probability": round(1.0 - fraud_prevented_rate, 4),
            "utility": utility,
        }

    @staticmethod
    def _variant(signals: Dict[str, Any], variant: str) -> Dict[str, Any]:
        """Apply attacker transformations to an otherwise observed feature set."""
        result = deepcopy(signals)
        if variant == "split_transfer":
            result["amount_anomaly"] = max(0.0, result["amount_anomaly"] - 0.25)
            result["velocity_30m"] = max(1, result["velocity_30m"] - 1)
        elif variant == "wait_between_transfers":
            result["velocity_30m"] = 1
            result["has_dormant_gap"] = True
            result["sequence_score"] = min(1.0, result["sequence_score"] + 0.1)
        elif variant == "rotate_device":
            result["new_device"] = False
            result["network_link_count"] = max(1, result["network_link_count"])
        elif variant == "beneficiary_hop":
            result["new_beneficiary"] = True
            result["network_link_count"] = max(1, result["network_link_count"])
        elif variant == "shadow_bypass":
            result["new_beneficiary"] = False
            result["new_device"] = False
            result["network_link_count"] = 0
            result["has_test_then_transfer"] = False
            result["sequence_score"] = 0.0
            result["amount_anomaly"] = min(0.2, result["amount_anomaly"])
            result["velocity_30m"] = 2
        return result

    def compare(self, controls: Iterable[DefenseCandidate] | None = None, variants: Iterable[str] | None = None) -> List[Dict[str, Any]]:
        """Compare each control across base and adversarial variants."""
        candidates = list(controls or default_defenses())
        attack_variants = list(variants or ["base", "split_transfer", "wait_between_transfers", "rotate_device", "beneficiary_hop"])
        results = []
        for candidate in candidates:
            base = self.evaluate(candidate, variant="base")
            variant_results = [self.evaluate(candidate, variant=variant) for variant in attack_variants if variant != "base"]
            result = {**base, "attack_variants": variant_results, "average_attack_success_probability": round(sum(item["attack_success_probability"] for item in variant_results + [base]) / (len(variant_results) + 1), 4)}
            results.append(result)
        return sorted(results, key=lambda item: (-item["utility"], item["control_id"]))

    def attacker_challenge(self, control: DefenseCandidate, round_number: int) -> Dict[str, Any]:
        """Generate an adaptive bypass from the control's actual predicates."""
        sequence = [
            ("split_transfer", "Split a high-value transfer into smaller payments to lower amount and velocity signals."),
            ("wait_between_transfers", "Wait between payments to evade short-window velocity checks."),
            ("rotate_device", "Rotate devices while preserving a relationship to the same beneficiary network."),
            ("shadow_bypass", "Use a trusted-looking proxy path that removes the original novelty markers while preserving attack velocity."),
        ]
        variant, statement = sequence[(round_number - 1) % len(sequence)]
        return {"round": round_number, "variant": variant, "statement": statement, "target_control": control.control_id}

    @staticmethod
    def revise_defense(control: DefenseCandidate, challenge: Dict[str, Any]) -> DefenseCandidate:
        """Add a transparent predicate targeted at the observed bypass."""
        revised = deepcopy(control)
        variant = challenge["variant"]
        if variant == "split_transfer":
            revised.conditions.append("sequence_score>=0.55")
            revised.action += "; correlate sequence rather than amount alone"
        elif variant == "wait_between_transfers":
            revised.conditions.append("test_then_transfer")
            revised.action += "; retain dormant-interval sequence evidence"
        elif variant == "rotate_device":
            revised.conditions.append("network_link>=1&new_beneficiary")
            revised.action += "; correlate linked entities across devices"
        else:
            revised.conditions.append("velocity_30m>=2")
            revised.action += "; correlate proxy-path velocity with the prior incident"
        revised.control_id = f"{control.control_id}-R{challenge['round']}"
        revised.name = f"{control.name} / revised {challenge['round']}"
        revised.rationale += " Revision is driven by the adaptive bypass observed in the bounded challenge loop."
        return revised

    def adversarial_loop(self, initial: DefenseCandidate | None = None, max_iterations: int = 3) -> Dict[str, Any]:
        """Run attack → defense → simulation → challenge until bounded convergence."""
        if max_iterations < 1 or max_iterations > 6:
            raise ValueError("max_iterations must be between 1 and 6")
        if initial is None:
            candidates = default_defenses()
            ranked = self.compare(candidates)
            best_id = ranked[0]["control_id"]
            current = deepcopy(next(candidate for candidate in candidates if candidate.control_id == best_id))
        else:
            current = deepcopy(initial)
        if isinstance(current, dict):
            current = DefenseCandidate(**{key: current[key] for key in ("control_id", "name", "action", "friction", "operational_cost", "conditions", "rationale")}, lifecycle=current.get("lifecycle", "RECOMMEND"))
        rounds = []
        previous_utility = None
        for round_number in range(1, max_iterations + 1):
            challenge = self.attacker_challenge(current, round_number)
            before = self.evaluate(current, variant=challenge["variant"])
            revised = self.revise_defense(current, challenge)
            after = self.evaluate(revised, variant=challenge["variant"])
            improvement = round(after["utility"] - before["utility"], 4)
            rounds.append({"round": round_number, "attacker": challenge, "defense_before": current.as_dict(), "simulation_before": before, "revised_defense": revised.as_dict(), "simulation_after": after, "utility_improvement": improvement})
            current = revised if improvement >= 0 else current
            if improvement <= 0 or (previous_utility is not None and abs(improvement) < 0.01):
                break
            previous_utility = improvement
        final = self.evaluate(current)
        return {"max_iterations": max_iterations, "iterations_executed": len(rounds), "converged": len(rounds) < max_iterations or rounds[-1]["utility_improvement"] <= 0.01, "selected_defense": current.as_dict(), "rounds": rounds, "final_simulation": final}
