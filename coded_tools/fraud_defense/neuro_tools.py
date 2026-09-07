"""Neuro SAN coded tools exposing the deterministic fraud workbench."""

from __future__ import annotations

import os
import asyncio
import time
from threading import Lock
from typing import Any
from typing import Dict
from typing import Type

from coded_tools.fraud_defense.orchestration import FraudDefenseEngine

try:  # Allows offline unit tests before the optional Neuro SAN runtime is installed.
    from neuro_san.interfaces.coded_tool import CodedTool
except ImportError:  # pragma: no cover - exercised only in dependency-light environments.
    class CodedTool:  # type: ignore[no-redef]
        """Compatibility base used only when the Neuro SAN package is absent."""


_ENGINE: FraudDefenseEngine | None = None
_ENGINE_LOCK = Lock()


def _engine() -> FraudDefenseEngine:
    """Reuse one deterministic environment per server process."""
    global _ENGINE  # pylint: disable=global-statement
    with _ENGINE_LOCK:
        if _ENGINE is None:
            _ENGINE = FraudDefenseEngine(seed=int(os.getenv("FRAUD_DATA_SEED", "17")), case_count=int(os.getenv("FRAUD_CASE_COUNT", "600")))
    return _ENGINE


class FraudWorkbenchTool(CodedTool):
    """Base class implementing safe case lookup and sly-data state updates."""

    action = "context"

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute one deterministic workbench action."""
        try:
            if not isinstance(args, dict) or not isinstance(sly_data, dict):
                raise ValueError("Tool arguments and sly_data must be objects")
            case_id = args.get("case_id") or sly_data.get("fraud_case_id")
            if not isinstance(case_id, str) or not case_id:
                if self.action != "cycle_gate":
                    raise ValueError("An explicit synthetic case_id is required")
                case_id = "CASE-0001"
            engine = await asyncio.to_thread(_engine)
            engine.environment.case(case_id)
            if sly_data.get("fraud_case_id") != case_id:
                sly_data["fraud_war_room"] = {}
                sly_data["fraud_cycle_state"] = {}
                sly_data.pop("decision_passport", None)
            sly_data["fraud_case_id"] = case_id
            state = sly_data.setdefault("fraud_war_room", {})
            if not isinstance(state, dict):
                raise ValueError("Invalid investigation state")
            if self.action == "cycle_gate":
                args = {**args, "_cycle_state": sly_data.setdefault("fraud_cycle_state", {})}
            # Keep the bulletin board internal to coded tools. It is shared
            # through sly_data and is never sent as an LLM argument.
            args = {**args, "_state": state}
            started = time.perf_counter()
            result = await asyncio.to_thread(self.run_action, engine, case_id, args)
            state.setdefault("audit_events", []).append({
                "case_id": case_id, "tool": type(self).__name__, "action": self.action,
                "status": "completed", "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                "source": "coded_tool",
            })
            sly_data["fraud_case_id"] = case_id
            state[self.action] = result
            if self.action == "decision_passport":
                sly_data["decision_passport"] = result
            if self.action == "cycle_gate":
                sly_data["fraud_cycle_state"]["iteration"] = result.get("iteration", 0)
            return result
        except (KeyError, TypeError, ValueError, OSError) as exc:
            return {"error": str(exc), "action": self.action, "recoverable": True}

    def run_action(self, engine: FraudDefenseEngine, case_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch a subclass action."""
        raise NotImplementedError


class GetCaseContext(FraudWorkbenchTool):
    """Return alert and customer/account context."""

    action = "case_context"

    def run_action(self, engine: FraudDefenseEngine, case_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
        return engine.case_context(case_id)


class AnalyzeTransactions(FraudWorkbenchTool):
    """Calculate exact transaction signals."""

    action = "transaction_analysis"

    def run_action(self, engine: FraudDefenseEngine, case_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
        return engine.analytics.signals(case_id)


class AnalyzeCustomer(FraudWorkbenchTool):
    """Calculate customer baseline behavior."""

    action = "customer_analysis"

    def run_action(self, engine: FraudDefenseEngine, case_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
        return engine.analytics.customer_profile(case_id)


class AnalyzeGraph(FraudWorkbenchTool):
    """Traverse connected campaign entities."""

    action = "graph_analysis"

    def run_action(self, engine: FraudDefenseEngine, case_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
        return engine.graph.findings(case_id)


class ReconstructTimeline(FraudWorkbenchTool):
    """Reconstruct chronological payment behavior."""

    action = "timeline_analysis"

    def run_action(self, engine: FraudDefenseEngine, case_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
        return engine.analytics.timeline(case_id)


class AssembleEvidence(FraudWorkbenchTool):
    """Assemble evidence from the prior deterministic analyst outputs."""

    action = "evidence_analysis"

    def run_action(self, engine: FraudDefenseEngine, case_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
        state = args.get("_state", {})
        bundle = engine.analysis_bundle(case_id)
        signals = state.get("transaction_analysis", bundle["signals"])
        graph = state.get("graph_analysis", bundle["graph"])
        timeline = state.get("timeline_analysis", bundle["timeline"])
        return engine._evidence(signals, graph, timeline)  # pylint: disable=protected-access


class GenerateHypotheses(FraudWorkbenchTool):
    """Generate competing explanations from deterministic evidence."""

    action = "hypotheses"

    def run_action(self, engine: FraudDefenseEngine, case_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
        state = args.get("_state", {})
        bundle = engine.analysis_bundle(case_id)
        hypotheses = engine._hypotheses(  # pylint: disable=protected-access
            state.get("transaction_analysis", bundle["signals"]),
            state.get("graph_analysis", bundle["graph"]),
        )
        evidence = state.get("evidence_analysis") or engine.evidence_for_case(case_id, bundle)
        return {"hypotheses": hypotheses, "counter_evidence": evidence["counter"]}


class ReconstructAttack(FraudWorkbenchTool):
    """Return the attack reconstruction and bounded loop."""

    action = "attack_reconstruction"

    def run_action(self, engine: FraudDefenseEngine, case_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
        return engine.reconstruct_attack_for_case(case_id)


class AttackChallenge(FraudWorkbenchTool):
    """Produce the next adaptive attacker variant."""

    action = "attacker_challenge"

    def run_action(self, engine: FraudDefenseEngine, case_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
        state = args.get("_state", {})
        selected = state.get("simulation", {}).get("selected_defense")
        if not selected:
            defenses = state.get("defense_candidates", {})
            candidates = defenses.get("defense_candidates", []) if isinstance(defenses, dict) else []
            selected = candidates[0] if candidates else engine.defense_candidates_for_case(case_id)[0]
        candidate = engine.candidate_from_dict(selected)
        round_number = int(args.get("round", state.get("cycle_gate", {}).get("iteration", 1)))
        return engine.simulator.attacker_challenge(candidate, round_number)


class ProposeDefenses(FraudWorkbenchTool):
    """Return distinct defender candidates."""

    action = "defense_candidates"

    def run_action(self, engine: FraudDefenseEngine, case_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
        state = args.get("_state", {})
        candidates = engine.defense_candidates_for_case(case_id)
        challenge = state.get("attacker_challenge")
        if challenge:
            selected = state.get("simulation", {}).get("selected_defense") or candidates[0]
            revised = engine.simulator.revise_defense(engine.candidate_from_dict(selected), challenge)
            candidates.append(revised.as_dict())
        return {"defense_candidates": candidates}


class SimulateDefenses(FraudWorkbenchTool):
    """Compare controls using synthetic counterfactual outcomes."""

    action = "simulation"

    def run_action(self, engine: FraudDefenseEngine, case_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
        state = args.get("_state", {})
        defenses = state.get("defense_candidates", {})
        candidates = defenses.get("defense_candidates", []) if isinstance(defenses, dict) else []
        simulations = engine.simulations_for_case(case_id, candidates)
        definitions = {item["control_id"]: item for item in candidates or engine.defense_candidates_for_case(case_id)}
        selected = definitions[simulations[0]["control_id"]] if simulations else {}
        return {"simulation_results": simulations, "selected_defense": selected}


class ChallengeDecision(FraudWorkbenchTool):
    """Return contradiction and missing-evidence challenge."""

    action = "decision_challenge"

    def run_action(self, engine: FraudDefenseEngine, case_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
        state = args.get("_state", {})
        bundle = engine.analysis_bundle(case_id)
        hypotheses_result = state.get("hypotheses", {})
        hypotheses = hypotheses_result.get("hypotheses", []) if isinstance(hypotheses_result, dict) else []
        hypotheses = hypotheses or engine.hypotheses_for_case(case_id, bundle)
        evidence = state.get("evidence_analysis") or engine.evidence_for_case(case_id, bundle)
        graph = state.get("graph_analysis", bundle["graph"])
        return engine._challenge(hypotheses, evidence, graph)  # pylint: disable=protected-access


class RouteModels(FraudWorkbenchTool):
    """Apply risk-adaptive provider selection and disagreement protocol."""

    action = "model_routing"

    def run_action(self, engine: FraudDefenseEngine, case_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
        return engine.model_routing_for_case(case_id)


class CheckGovernance(FraudWorkbenchTool):
    """Evaluate human approval, simulation, evidence, and shadow policies."""

    action = "governance"

    def run_action(self, engine: FraudDefenseEngine, case_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
        return engine.governance_for_case(case_id, args.get("_state", {}))


class CreateDecisionPassport(FraudWorkbenchTool):
    """Create the auditable decision passport."""

    action = "decision_passport"

    def run_action(self, engine: FraudDefenseEngine, case_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
        return engine.create_passport_from_state(case_id, args.get("_state", {}))


class RecordOutcome(FraudWorkbenchTool):
    """Record explicit predicted-versus-observed outcomes after approval."""

    action = "outcome_learning"

    def run_action(self, engine: FraudDefenseEngine, case_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
        state = args.get("_state", {})
        simulation = state.get("simulation", {})
        # An LLM-supplied boolean (or client sly_data) is not human authorization.
        return {"status": "awaiting_human_approval", "case_id": case_id,
                "reason": "Record approval and outcomes through the investigator interface."}


class CycleGate(FraudWorkbenchTool):
    """Bound the HOCON attacker/defender/challenger cycle."""

    action = "cycle_gate"

    def run_action(self, engine: FraudDefenseEngine, case_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
        del engine, case_id
        state = args.setdefault("_cycle_state", {}) if isinstance(args.get("_cycle_state"), dict) else {}
        iteration = int(state.get("iteration", 0)) + 1
        configured = max(1, min(6, int(os.getenv("FRAUD_MAX_ATTACK_ROUNDS", "3"))))
        maximum = min(configured, int(args.get("max_iterations", configured)))
        if maximum < 1:
            raise ValueError("max_iterations must be positive")
        return {"iteration": iteration, "max_iterations": maximum, "continue": iteration <= maximum}


TOOL_CLASSES: Dict[str, Type[FraudWorkbenchTool]] = {
    "GetCaseContext": GetCaseContext,
    "AnalyzeTransactions": AnalyzeTransactions,
    "AnalyzeCustomer": AnalyzeCustomer,
    "AnalyzeGraph": AnalyzeGraph,
    "ReconstructTimeline": ReconstructTimeline,
    "AssembleEvidence": AssembleEvidence,
    "GenerateHypotheses": GenerateHypotheses,
    "ReconstructAttack": ReconstructAttack,
    "AttackChallenge": AttackChallenge,
    "ProposeDefenses": ProposeDefenses,
    "SimulateDefenses": SimulateDefenses,
    "ChallengeDecision": ChallengeDecision,
    "RouteModels": RouteModels,
    "CheckGovernance": CheckGovernance,
    "CreateDecisionPassport": CreateDecisionPassport,
    "RecordOutcome": RecordOutcome,
    "CycleGate": CycleGate,
}
