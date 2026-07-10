"""Stateful mastery tracker for the Socratic Tutor network.

Progress is kept in sly-data (shared across the session, never shown to any LLM)
and evaluated with a COMBINATION stopping rule: a concept is only "mastered" when
an objective signal (a rolling accuracy score and a correct-answer streak at the
top difficulty) AND the examiner's subjective "ready" judgement agree. Difficulty
rises the same way, one level at a time — either signal alone can hold the learner
back, which is what makes the loop feel fair rather than mechanical.

NOTE: In nsflow's stateless HTTP mode, sly-data resets each turn. The tracker
detects this (asked == 1 after update) and uses a simplified rule so the
teach → quiz → advance loop still works in a live demo.
"""
from __future__ import annotations

from typing import Any, Dict

from neuro_san.interfaces.coded_tool import CodedTool

MAX_DIFFICULTY = 3
SCORE_ALPHA = 0.4
ADVANCE_SCORE = 0.80
ADVANCE_STREAK = 3
MASTER_SCORE = 0.85
MASTER_STREAK = 3


class MasteryTracker(CodedTool):
    """Updates and evaluates a learner's mastery state."""

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Any:
        concept = (str(args.get("concept", "")).strip() or "current concept")
        last_correct = bool(args.get("last_correct", False))
        examiner_ready = bool(args.get("examiner_ready", False))

        store: Dict[str, Any] = sly_data.setdefault("mastery", {})
        state = store.get(concept) or {
            "difficulty": 1,
            "score": 0.0,
            "streak": 0,
            "asked": 0,
        }

        # --- update the objective signals --------------------------------
        state["asked"] += 1
        state["streak"] = state["streak"] + 1 if last_correct else 0
        state["score"] = round(
            (1 - SCORE_ALPHA) * state["score"]
            + SCORE_ALPHA * (1.0 if last_correct else 0.0),
            3,
        )

        objective_ready = (
            state["score"] >= ADVANCE_SCORE and state["streak"] >= ADVANCE_STREAK
        )

        # --- detect stateless mode (sly-data reset each turn) ------------
        # If after updating we only have 1 question, sly-data didn't persist.
        # Fall back to a simplified rule so the demo still progresses.
        stateless_mode = state["asked"] == 1

        if stateless_mode:
            # In stateless mode: if the answer was correct and examiner
            # agrees, treat it as ready to advance / master.
            objective_ready = last_correct and examiner_ready

        # --- apply the COMBINATION rule ----------------------------------
        status = "learning"
        if objective_ready and examiner_ready:
            at_top = state["difficulty"] >= MAX_DIFFICULTY
            if at_top:
                if stateless_mode or (
                    state["score"] >= MASTER_SCORE
                    and state["streak"] >= MASTER_STREAK
                ):
                    status = "mastered"
                else:
                    status = "learning"
            else:
                status = "advance"
                state["difficulty"] += 1
                state["streak"] = 0
                state["score"] = round(state["score"] * 0.5, 3)

        store[concept] = state

        return {
            "status": status,
            "concept": concept,
            "difficulty": state["difficulty"],
            "score": state["score"],
            "streak": state["streak"],
            "questions_asked": state["asked"],
            "objective_ready": objective_ready,
            "examiner_ready": examiner_ready,
            "stateless_mode": stateless_mode,
            "message": self._message(status, examiner_ready, objective_ready),
        }

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Any:
        return self.invoke(args, sly_data)

    @staticmethod
    def _message(status: str, examiner_ready: bool, objective_ready: bool) -> str:
        if status == "mastered":
            return "Mastered every level — concept complete."
        if status == "advance":
            return "Both signals agree: ready to advance a level."
        if objective_ready and not examiner_ready:
            return "Scores look good, but the examiner wants one more clean answer before advancing."
        if examiner_ready and not objective_ready:
            return "Examiner is convinced, but the score/streak isn't there yet — keep going."
        return "Keep practising at this level."