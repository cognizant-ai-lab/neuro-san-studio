"""Closed-loop Fraud War Room application orchestration."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List

from coded_tools.fraud_defense.analytics import FraudGraph
from coded_tools.fraud_defense.analytics import TransactionAnalytics
from coded_tools.fraud_defense.generator import generate_environment
from coded_tools.fraud_defense.learning import LearningStore
from coded_tools.fraud_defense.models import AgentEvent
from coded_tools.fraud_defense.models import RiskLevel
from coded_tools.fraud_defense.models import SyntheticEnvironment
from coded_tools.fraud_defense.passport import build_passport
from coded_tools.fraud_defense.policy import governance_check
from coded_tools.fraud_defense.risk import investigation_plan
from coded_tools.fraud_defense.risk import risk_level
from coded_tools.fraud_defense.router import ModelRouter
from coded_tools.fraud_defense.simulation import DefenseCandidate
from coded_tools.fraud_defense.simulation import DefenseSimulator
from coded_tools.fraud_defense.simulation import default_defenses


NETWORK_AGENTS = [
    "fraud_commander", "transaction_analyst", "customer_analyst", "entity_graph_analyst", "timeline_process_analyst",
    "evidence_analyst", "hypothesis_generator", "attack_reconstructor", "attacker_agent", "defender_agent",
    "counterfactual_simulator", "adversarial_challenger", "model_router", "policy_governance", "decision_governor", "outcome_learning",
]


class FraudDefenseEngine:
    """Coordinate deterministic workbench capabilities for a full demo cycle.

    The engine is the application/workbench layer. The actual LLM agent routing
    is declared separately in ``registries/industry/fraud_defense.hocon`` and
    calls these same capabilities through Neuro SAN coded tools.
    """

    def __init__(self, environment: SyntheticEnvironment | None = None, *, seed: int = 17, case_count: int = 600, artifact_dir: str | Path = "artifacts"):
        self.environment = environment or generate_environment(seed=seed, case_count=case_count)
        self.analytics = TransactionAnalytics(self.environment)
        self.graph = FraudGraph(self.environment)
        self.simulator = DefenseSimulator(self.environment, self.analytics)
        self.router = ModelRouter()
        self.learning = LearningStore(Path(artifact_dir) / "fraud_learning.json")
        self._results: Dict[str, Dict[str, Any]] = {}

    def case_context(self, case_id: str) -> Dict[str, Any]:
        """Return customer/account/alert context safe for investigator display."""
        case = self.environment.public_case(case_id)
        alert = next(alert for alert in self.environment.alerts if alert["case_id"] == case_id)
        customer = next(customer for customer in self.environment.customers if customer["customer_id"] == case["customer_id"])
        account = next(account for account in self.environment.accounts if account["account_id"] == case["account_id"])
        return {
            "case": case,
            "alert": alert,
            "customer": customer,
            "account": account,
            "transactions": self.analytics.current_transactions(case_id),
            "historical_profile": self.analytics.customer_profile(case_id),
        }

    @staticmethod
    def _evidence(signals: Dict[str, Any], graph: Dict[str, Any], timeline: Dict[str, Any]) -> Dict[str, Any]:
        """Separate facts, counter-evidence, and missing evidence."""
        supporting = [
            {"evidence_id": "E-TXN-001", "type": "transaction", "fact": f"Latest transaction is {signals['amount_ratio_to_median']}x the historical median."},
            {"evidence_id": "E-TXN-002", "type": "behavior", "fact": f"{signals['velocity_30m']} current events fall inside a 30-minute window."},
            {"evidence_id": "E-CUST-001", "type": "customer_baseline", "fact": f"New beneficiary={signals['new_beneficiary']} and new device={signals['new_device']} against observed history."},
            {"evidence_id": "E-TIME-001", "type": "timeline", "fact": f"Observed process sequence: {' → '.join(timeline['sequence'])}."},
            {"evidence_id": "E-GRAPH-001", "type": "graph", "fact": f"Entity component contains {graph['component_size']} nodes and {len(graph['linked_accounts'])} linked accounts."},
        ]
        counter = [
            {"evidence_id": "E-COUNTER-001", "type": "counter_evidence", "fact": "Customer has an established account tenure and a non-empty normal transaction history."},
            {"evidence_id": "E-COUNTER-002", "type": "counter_evidence", "fact": "Behavioral signals alone cannot prove unauthorized intent."},
        ]
        missing = []
        if not signals["new_location"]:
            missing.append({"evidence_id": "E-MISSING-LOCATION", "fact": "Independent location corroboration is unavailable."})
        if not graph["campaign_signal"]:
            missing.append({"evidence_id": "E-MISSING-NETWORK", "fact": "No campaign-level relationship has been established."})
        missing.append({"evidence_id": "E-MISSING-HUMAN", "fact": "Customer confirmation of transaction intent is pending."})
        return {"supporting": supporting, "counter": counter, "missing": missing}

    @staticmethod
    def _hypotheses(signals: Dict[str, Any], graph: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate competing explanations from facts, not a single conclusion."""
        takeover = min(0.96, 0.35 + 0.22 * bool(signals["new_device"]) + 0.18 * bool(signals["new_beneficiary"]) + 0.14 * bool(signals["new_location"]) + 0.12 * bool(signals["has_test_then_transfer"]))
        authorized = max(0.06, 0.42 - 0.16 * bool(signals["new_device"]) - 0.10 * bool(signals["has_test_then_transfer"]))
        campaign = min(0.95, 0.16 + 0.28 * bool(graph["campaign_signal"]) + 0.18 * min(1, len(graph["linked_accounts"]) / 3) + 0.18 * bool(signals["has_test_then_transfer"]))
        return [
            {"hypothesis_id": "H1", "label": "account takeover with beneficiary setup", "confidence": round(takeover, 3), "status": "supported" if takeover >= authorized else "open"},
            {"hypothesis_id": "H2", "label": "authorized but unusual high-value activity", "confidence": round(authorized, 3), "status": "counter_explanation"},
            {"hypothesis_id": "H3", "label": "coordinated payment-fraud campaign", "confidence": round(campaign, 3), "status": "supported" if graph["campaign_signal"] else "requires_network_evidence"},
        ]

    @staticmethod
    def _challenge(hypotheses: List[Dict[str, Any]], evidence: Dict[str, Any], graph: Dict[str, Any]) -> Dict[str, Any]:
        """Challenge unsupported conclusions and name the next evidence request."""
        leader = max(hypotheses, key=lambda item: item["confidence"])
        return {
            "challenged_hypothesis": leader["hypothesis_id"],
            "challenge": "The leading hypothesis is plausible but behavioral novelty is not proof of unauthorized intent.",
            "contradictory_evidence": [item["fact"] for item in evidence["counter"]],
            "additional_evidence_requested": ["customer confirmation", "beneficiary ownership verification", "device-to-entity relationship review"],
            "campaign_signal_rechecked": graph["campaign_signal"],
            "resolution": "retain escalation because supporting and counter-evidence coexist",
        }

    def analysis_bundle(self, case_id: str) -> Dict[str, Any]:
        """Return the deterministic facts an agent needs for one case.

        This is deliberately a workbench primitive, not an agent orchestrator.
        Neuro SAN agents call the individual coded tools and exchange their
        compact results through ``sly_data``.
        """
        context = self.case_context(case_id)
        signals = self.analytics.signals(case_id)
        graph = self.graph.findings(case_id)
        timeline = self.analytics.timeline(case_id)
        level = risk_level(signals["risk_score"])
        return {
            "context": context,
            "signals": signals,
            "graph": graph,
            "timeline": timeline,
            "risk_level": level,
            "investigation_plan": investigation_plan(level),
        }

    def evidence_for_case(self, case_id: str, bundle: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Separate deterministic facts, counter-evidence, and missing evidence."""
        bundle = bundle or self.analysis_bundle(case_id)
        return self._evidence(bundle["signals"], bundle["graph"], bundle["timeline"])

    def hypotheses_for_case(self, case_id: str, bundle: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        """Generate competing explanations from the current evidence bundle."""
        bundle = bundle or self.analysis_bundle(case_id)
        return self._hypotheses(bundle["signals"], bundle["graph"])

    def reconstruct_attack_for_case(self, case_id: str, bundle: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Describe observed attack stages without asserting hidden intent."""
        bundle = bundle or self.analysis_bundle(case_id)
        timeline = bundle["timeline"]
        graph = bundle["graph"]
        return {
            "case_id": case_id,
            "observed_stages": [
                {"phase": event["phase"], "transaction_id": event["transaction_id"], "timestamp": event["timestamp"]}
                for event in timeline["events"]
            ],
            "observed_sequence": timeline["sequence"],
            "connected_accounts": graph["linked_accounts"],
            "central_entities": graph["central_entities"][:5],
            "likely_objective": "move value toward connected accounts" if "laundering" in timeline["sequence"] else "complete an unauthorized payment objective",
            "boundary": "The sequence is observed behavior; attacker intent remains a hypothesis.",
        }

    def defense_candidates_for_case(self, case_id: str | None = None) -> List[Dict[str, Any]]:
        """Return distinct controls for a defender agent to compare."""
        del case_id
        return [candidate.as_dict() for candidate in default_defenses()]

    def simulations_for_case(self, case_id: str | None = None, candidates: List[Dict[str, Any]] | None = None) -> List[Dict[str, Any]]:
        """Run counterfactual control comparisons over the synthetic environment."""
        del case_id
        candidate_objects = [self.candidate_from_dict(candidate) for candidate in candidates] if candidates else default_defenses()
        return self.simulator.compare(candidate_objects)

    def model_routing_for_case(self, case_id: str) -> Dict[str, Any]:
        """Route independent provider or offline opinions by computed risk."""
        bundle = self.analysis_bundle(case_id)
        return self.router.assess(bundle["signals"], bundle["graph"], bundle["risk_level"]).as_dict()

    def governance_for_case(self, case_id: str, state: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Evaluate policy using only the evidence and simulations currently available."""
        state = state or {}
        bundle = self.analysis_bundle(case_id)
        evidence = state.get("evidence_analysis") or self.evidence_for_case(case_id, bundle)
        simulation = state.get("simulation") or {}
        simulations = simulation.get("simulation_results", []) if isinstance(simulation, dict) else []
        routing = state.get("model_routing") or self.model_routing_for_case(case_id)
        evidence_count = len(evidence.get("supporting", [])) + len(evidence.get("counter", []))
        return governance_check(bundle["risk_level"], simulations, routing.get("disagreement", {}), evidence_count, "RECOMMEND")

    def create_passport_from_state(self, case_id: str, state: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Build the passport from coded-tool outputs shared by Neuro SAN agents."""
        state = state or {}
        bundle = self.analysis_bundle(case_id)
        evidence = state.get("evidence_analysis") or self.evidence_for_case(case_id, bundle)
        hypotheses_result = state.get("hypotheses") or {}
        hypotheses = hypotheses_result.get("hypotheses", []) if isinstance(hypotheses_result, dict) else []
        hypotheses = hypotheses or self.hypotheses_for_case(case_id, bundle)
        attack = state.get("attack_reconstruction") or self.reconstruct_attack_for_case(case_id, bundle)
        challenge = state.get("decision_challenge") or self._challenge(hypotheses, evidence, bundle["graph"])
        attacker_analysis = {"reconstruction": attack, "decision_challenge": challenge}
        if state.get("attacker_challenge"):
            attacker_analysis["adaptive_challenge"] = state["attacker_challenge"]
        defenses_result = state.get("defense_candidates") or {}
        defenses = defenses_result.get("defense_candidates", []) if isinstance(defenses_result, dict) else []
        simulations_result = state.get("simulation") or {}
        simulations = simulations_result.get("simulation_results", []) if isinstance(simulations_result, dict) else []
        selected = simulations_result.get("selected_defense", {}) if isinstance(simulations_result, dict) else {}
        selected = selected or (simulations[0] if simulations else {})
        routing = state.get("model_routing") or self.model_routing_for_case(case_id)
        governance = state.get("governance") or self.governance_for_case(case_id, state)
        confidence_values = [item.get("confidence", 0.0) for item in routing.get("assessments", [])]
        confidence = sum(confidence_values) / len(confidence_values) if confidence_values else max(item["confidence"] for item in hypotheses)
        decision = "hold_and_escalate" if bundle["risk_level"] in {RiskLevel.HIGH, RiskLevel.CRITICAL} else "step_up_for_review"
        if not governance["all_passed"]:
            decision = "request_more_investigation"
        adversarial = bundle["risk_level"] in {RiskLevel.HIGH, RiskLevel.CRITICAL} and bool(state.get("attacker_challenge") or attack)
        return build_passport(
            case_id, bundle["risk_level"], bundle["context"]["alert"], hypotheses, evidence, bundle["graph"], bundle["timeline"], routing,
            attacker_analysis, defenses, simulations, selected, governance, decision, confidence, bundle["signals"]["reason_codes"],
            deepcopy(state.get("audit_events", [])), "RECOMMEND", created_at=bundle["context"]["case"]["opened_at"],
        )

    def record_outcome_for_case(self, case_id: str, selected: Dict[str, Any], predicted: Dict[str, Any], approved: bool) -> Dict[str, Any]:
        """Record an explicit outcome after a human decision in the network."""
        if not approved:
            return {"status": "not_recorded", "reason": "human_rejected"}
        candidate = self.candidate_from_dict(selected) if selected else None
        hidden = self.environment.case(case_id)["ground_truth"]
        triggered = bool(candidate and self.simulator.triggers(candidate, self.simulator.signals_for_case(case_id)))
        observed = {
            "fraud_prevented_rate": 1.0 if triggered and hidden["fraud"] else 0.0,
            "false_positive_rate": 1.0 if triggered and not hidden["fraud"] else 0.0,
        }
        return self.learning.record(
            case_id, hidden["scenario"], selected,
            {key: float(predicted.get(key, 0.0)) for key in ("fraud_prevented_rate", "false_positive_rate")}, observed,
        )

    @staticmethod
    def candidate_from_dict(value: Dict[str, Any]) -> DefenseCandidate:
        """Normalize simulation output back to a candidate object."""
        return DefenseCandidate(
            value["control_id"], value["name"], value["action"], value["friction"], float(value["operational_cost"]),
            list(value["conditions"]), value["rationale"], value.get("lifecycle", "RECOMMEND"),
        )

    @staticmethod
    def _events(level: RiskLevel, simulation: bool, adversarial: bool, disagreement: bool) -> List[AgentEvent]:
        """Create observable phase events for the dashboard and audit trail."""
        events = [
            AgentEvent("fraud_commander", "opened_investigation", "DETECT", latency_ms=14, summary="Alert accepted and investigation plan selected."),
            AgentEvent("transaction_analyst", "calculated_behavioral_signals", "INVESTIGATE", latency_ms=21, confidence=0.87, evidence_reference="E-TXN-001", summary="Velocity, amount, novelty, and sequence features calculated."),
            AgentEvent("customer_analyst", "built_customer_baseline", "UNDERSTAND", latency_ms=18, confidence=0.78, evidence_reference="E-CUST-001", summary="Historical behavior separated unusual activity from normal patterns."),
            AgentEvent("entity_graph_analyst", "traversed_campaign_graph", "UNDERSTAND", latency_ms=26, confidence=0.84, evidence_reference="E-GRAPH-001", summary="Connected accounts, devices, and beneficiaries ranked deterministically."),
            AgentEvent("timeline_process_analyst", "reconstructed_sequence", "UNDERSTAND", latency_ms=19, confidence=0.81, evidence_reference="E-TIME-001", summary="Event chain reconstructed in chronological order."),
            AgentEvent("evidence_analyst", "separated_facts_from_hypotheses", "INVESTIGATE", latency_ms=23, confidence=0.86, evidence_reference="E-COUNTER-001", summary="Supporting, counter-, and missing evidence recorded."),
            AgentEvent("hypothesis_generator", "generated_competing_explanations", "INVESTIGATE", latency_ms=17, confidence=0.76, summary="Three explanations retained for challenge."),
        ]
        if level in {RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL}:
            events.append(AgentEvent("adversarial_challenger", "tested_leading_hypothesis", "CHALLENGE", latency_ms=22, confidence=0.74, escalation=disagreement, summary="Counter-evidence and missing-evidence requests attached."))
        if adversarial:
            events.extend([
                AgentEvent("attack_reconstructor", "reconstructed_attack_path", "ATTACK", latency_ms=24, confidence=0.82, summary="Attack stages mapped to the observed sequence."),
                AgentEvent("attacker_agent", "generated_bypass_variant", "ATTACK", latency_ms=31, confidence=0.77, summary="Adaptive bypass challenged the current control."),
                AgentEvent("defender_agent", "proposed_revised_controls", "DEFEND", latency_ms=29, confidence=0.83, summary="Relationship and sequence-aware controls proposed."),
                AgentEvent("counterfactual_simulator", "simulated_control_candidates", "SIMULATE", latency_ms=34, confidence=0.92, summary="Fraud loss, false positives, friction, cost, and latency compared."),
            ])
        events.extend([
            AgentEvent("policy_governance", "checked_policy_and_approval", "GOVERN", latency_ms=16, confidence=0.98, escalation=level in {RiskLevel.HIGH, RiskLevel.CRITICAL}, summary="Human approval and shadow-first rules evaluated."),
            AgentEvent("decision_governor", "issued_decision_passport", "DECIDE", latency_ms=27, confidence=0.89, escalation=level in {RiskLevel.HIGH, RiskLevel.CRITICAL}, summary="Auditable recommendation generated without chain-of-thought."),
        ])
        if simulation:
            events.append(AgentEvent("outcome_learning", "prepared_outcome_baseline", "LEARN", latency_ms=12, summary="Predicted outcome is ready for comparison after approval."))
        return events

    def investigate(self, case_id: str = "CASE-0001", *, max_attack_rounds: int = 3) -> Dict[str, Any]:
        """Run DETECT → INVESTIGATE → ATTACK → DEFEND → SIMULATE → GOVERN."""
        if case_id in self._results:
            return deepcopy(self._results[case_id])
        context = self.case_context(case_id)
        signals = self.analytics.signals(case_id)
        graph = self.graph.findings(case_id)
        timeline = self.analytics.timeline(case_id)
        level = risk_level(signals["risk_score"])
        plan = investigation_plan(level)
        hypotheses = self._hypotheses(signals, graph)
        evidence = self._evidence(signals, graph, timeline)
        routing = self.router.assess(signals, graph, level).as_dict()
        challenge = self._challenge(hypotheses, evidence, graph) if level != RiskLevel.LOW else {}
        candidates = default_defenses() if plan.get("simulation_required") else []
        simulations = self.simulator.compare(candidates) if candidates else []
        best_candidate = next((candidate for candidate in candidates if candidate.control_id == simulations[0]["control_id"]), None) if simulations else None
        adversarial = self.simulator.adversarial_loop(best_candidate, max_iterations=max_attack_rounds) if level in {RiskLevel.HIGH, RiskLevel.CRITICAL} else {"iterations_executed": 0, "converged": True, "rounds": [], "selected_defense": best_candidate.as_dict() if best_candidate else {}, "final_simulation": simulations[0] if simulations else {}}
        selected_defense = adversarial.get("selected_defense", {})
        governance = governance_check(level, simulations, routing.get("disagreement", {}), len(evidence["supporting"]) + len(evidence["counter"]), "RECOMMEND")
        confidence_values = [item.get("confidence", 0.0) for item in routing.get("assessments", [])]
        confidence = (sum(confidence_values) / len(confidence_values)) if confidence_values else max(item["confidence"] for item in hypotheses)
        if challenge and challenge.get("resolution"):
            confidence = max(0.0, confidence - 0.04)
        decision = "hold_and_escalate" if level in {RiskLevel.HIGH, RiskLevel.CRITICAL} else ("step_up_for_review" if level == RiskLevel.MEDIUM else "monitor")
        if not governance["all_passed"]:
            decision = "request_more_investigation"
        events = self._events(level, bool(simulations), bool(adversarial.get("rounds")), routing.get("disagreement", {}).get("triggered", False))
        audit_events = [event.as_dict() for event in events]
        passport = build_passport(
            case_id, level, context["alert"], hypotheses, evidence, graph, timeline, routing, {"challenge": challenge, "loop": adversarial},
            [candidate.as_dict() for candidate in candidates], simulations, selected_defense, governance, decision, confidence,
            signals["reason_codes"], audit_events, "RECOMMEND",
            created_at=context["case"]["opened_at"],
        )
        result = {
            "case_id": case_id,
            "context": context,
            "risk_level": level.value,
            "risk_score": signals["risk_score"],
            "investigation_plan": plan,
            "signals": signals,
            "graph": self.graph.public_subgraph(case_id),
            "graph_findings": graph,
            "timeline": timeline,
            "hypotheses": hypotheses,
            "evidence": evidence,
            "challenge": challenge,
            "model_routing": routing,
            "attacker_analysis": adversarial,
            "defense_candidates": [candidate.as_dict() for candidate in candidates],
            "simulation_results": simulations,
            "selected_defense": selected_defense,
            "governance": governance,
            "decision": decision,
            "confidence": round(confidence, 3),
            "agent_activity": [event.as_dict() for event in events],
            "deployment": {"lifecycle": "RECOMMEND", "approval": "pending", "variant_status": "not_started"},
            "decision_passport": passport,
            "learning": {"status": "awaiting_human_approval", "records": len(self.learning.read())},
        }
        self._results[case_id] = result
        return deepcopy(result)

    def approve(self, case_id: str, approved: bool) -> Dict[str, Any]:
        """Record investigator approval/rejection; approved controls enter SHADOW only."""
        result = self.investigate(case_id)
        if type(approved) is not bool:
            raise ValueError("Approval must be an explicit boolean")
        if approved and (not result["governance"]["all_passed"] or not result["simulation_results"]):
            raise ValueError("Governance and simulation must pass before approval")
        if approved and result["deployment"]["approval"] == "approved":
            return result
        level = RiskLevel(result["risk_level"])
        if approved:
            lifecycle = "SHADOW"
            decision = "approved_for_shadow"
            selected = result["selected_defense"]
            candidate = self.candidate_from_dict(selected) if selected else None
            predicted = result["simulation_results"][0] if result["simulation_results"] else {}
            observed = {"fraud_prevented_rate": 1.0 if candidate and self.simulator.triggers(candidate, self.simulator.signals_for_case(case_id)) and self.environment.case(case_id)["ground_truth"]["fraud"] else 0.0, "false_positive_rate": 1.0 if candidate and self.simulator.triggers(candidate, self.simulator.signals_for_case(case_id)) and not self.environment.case(case_id)["ground_truth"]["fraud"] else 0.0}
            learning = self.learning.record(case_id, self.environment.case(case_id)["ground_truth"]["scenario"], selected, {key: float(predicted.get(key, 0.0)) for key in ("fraud_prevented_rate", "false_positive_rate")}, observed)
        else:
            lifecycle = "RECOMMEND"
            decision = "rejected_by_human"
            learning = {"status": "not_recorded"}
        event = {"agent": "human_investigator", "action": "approve" if approved else "reject", "phase": "APPROVE", "status": "completed", "summary": f"Human decision recorded; lifecycle remains {lifecycle}."}
        result["deployment"] = {"lifecycle": lifecycle, "approval": "approved" if approved else "rejected", "variant_status": "ready_for_observation" if approved else "stopped"}
        result["decision"] = decision
        result["learning"] = learning
        result["agent_activity"].append(event)
        result["decision_passport"]["decision"] = decision
        result["decision_passport"]["deployment_lifecycle"] = lifecycle
        result["decision_passport"]["audit_events"].append(event)
        result["decision_passport"]["human_approval_required"] = level in {RiskLevel.HIGH, RiskLevel.CRITICAL}
        self._results[case_id] = result
        return deepcopy(result)

    def request_more_investigation(self, case_id: str) -> Dict[str, Any]:
        """Record a human request for more evidence without changing lifecycle."""
        result = self.investigate(case_id)
        event = AgentEvent("human_investigator", "request_more_investigation", "APPROVE", latency_ms=0, escalation=True, summary="Human requested additional evidence before a control decision.").as_dict()
        result["decision"] = "request_more_investigation"
        result["deployment"]["approval"] = "pending"
        result["deployment"]["variant_status"] = "evidence_requested"
        result["agent_activity"].append(event)
        result["decision_passport"]["decision"] = "request_more_investigation"
        result["decision_passport"]["audit_events"].append(event)
        result["learning"] = {"status": "awaiting_additional_evidence", "records": len(self.learning.read())}
        self._results[case_id] = result
        return deepcopy(result)

    def advance_shadow(self, case_id: str = "CASE-0001") -> Dict[str, Any]:
        """Introduce a new attacker variant and produce a revised shadow control."""
        if case_id not in self._results or self._results[case_id]["deployment"]["approval"] != "approved":
            raise ValueError("Explicit human approval is required before shadow observation")
        result = deepcopy(self._results[case_id])
        if result["deployment"]["lifecycle"] != "SHADOW":
            return deepcopy(result)
        selected = self.candidate_from_dict(result["selected_defense"])
        round_number = max(4, int(result["attacker_analysis"].get("iterations_executed", 1)) + 1)
        challenge = self.simulator.attacker_challenge(selected, round_number)
        transformed = self.simulator._variant(self.simulator.signals_for_case(case_id), challenge["variant"])
        bypass_detected = not self.simulator.triggers(selected, transformed)
        revised = self.simulator.revise_defense(selected, challenge) if bypass_detected else selected
        result["deployment"]["variant_status"] = "BYPASS_DETECTED" if bypass_detected else "variant_contained"
        result["deployment"]["attacker_variant"] = challenge
        result["deployment"]["revised_defense"] = revised.as_dict()
        result["agent_activity"].extend([
            AgentEvent("attacker_agent", "introduced_shadow_variant", "OBSERVE", latency_ms=18, summary=challenge["statement"]).as_dict(),
            AgentEvent("defender_agent", "revised_shadow_control", "LEARN", latency_ms=22, summary="New relationship/sequence predicate added after bypass detection.").as_dict(),
        ])
        result["decision_passport"]["attacker_analysis"]["shadow_variant"] = challenge
        result["decision_passport"]["attacker_analysis"]["bypass_detected"] = bypass_detected
        result["deployment"]["revision_simulation"] = self.simulator.evaluate(revised)
        result["deployment"]["revision_approval"] = "pending" if bypass_detected else "not_required"
        self._results[case_id] = result
        return deepcopy(result)

    def list_cases(self, limit: int = 30) -> List[Dict[str, Any]]:
        """List public alerts for the investigator queue."""
        rows = []
        for case in self.environment.cases[:limit]:
            signals = self.analytics.signals(case["case_id"])
            rows.append({"case_id": case["case_id"], "customer_id": case["customer_id"], "priority": case["priority"], "scenario": case["scenario"], "risk_score": signals["risk_score"], "status": self._results.get(case["case_id"], {}).get("deployment", {}).get("lifecycle", "OPEN")})
        return rows

    def demo(self, case_id: str = "CASE-0001") -> Dict[str, Any]:
        """Run the flagship alert through approval and one shadow variation."""
        self.investigate(case_id)
        self.approve(case_id, True)
        return self.advance_shadow(case_id)
