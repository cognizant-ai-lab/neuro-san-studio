"""Deterministic math answer checker for the Socratic Tutor network.

Correctness is computed in code (via sympy), never left to the LLM. This is the
"coded tool does real work" piece of the project and it removes the classic
failure mode where a language model mis-grades fraction arithmetic.

Two problem shapes are supported (the ones the examiner is told to produce):
  * arithmetic / fraction expressions, e.g. "3/4 + 1/6"
  * linear (or simple) equations,      e.g. "solve 2*x + 3 = 7 for x"
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

from neuro_san.interfaces.coded_tool import CodedTool

# Let learners write "2x" for 2*x and "^" for exponent.
_TRANSFORMS = standard_transformations + (
    implicit_multiplication_application,
    convert_xor,
)


class AnswerChecker(CodedTool):
    """Checks a learner's math answer against the correct value."""

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Any:
        problem = str(args.get("problem", "")).strip()
        student = str(args.get("student_answer", "")).strip()

        if not problem or not student:
            return {"correct": False, "error": "Missing problem or student_answer."}

        try:
            expected_val, expected_str = self._solve(problem)
        except Exception as exc:  # noqa: BLE001 - surface parse issues to the agent
            return {"correct": False, "error": f"Could not parse problem: {exc}",
                    "problem": problem}

        try:
            student_val = self._parse_student(student)
        except Exception as exc:  # noqa: BLE001
            return {"correct": False, "expected": expected_str,
                    "error": f"Could not parse answer: {exc}", "problem": problem}

        try:
            correct = self._equal(expected_val, student_val)
        except Exception:  # noqa: BLE001
            correct = False

        return {
            "correct": bool(correct),
            "expected": expected_str,
            "student_answer": student,
            "problem": problem,
        }

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Any:
        return self.invoke(args, sly_data)

    # ------------------------------------------------------------------ #
    # helpers
    # ------------------------------------------------------------------ #
    def _solve(self, problem: str) -> Tuple[Any, str]:
        """Return (value, pretty_string) for the given problem."""
        work = problem.strip().lower()
        work = re.sub(r"^\s*solve\s+", "", work)          # drop a leading "solve"

        var_match = re.search(r"\bfor\s+([a-z])\b", work)  # capture "for x"
        var_name: Optional[str] = var_match.group(1) if var_match else None
        work = re.sub(r"\bfor\s+[a-z]\b", "", work).strip()

        if "=" in work:
            left, right = work.split("=", 1)
            lhs = parse_expr(left, transformations=_TRANSFORMS)
            rhs = parse_expr(right, transformations=_TRANSFORMS)
            equation = sp.Eq(lhs, rhs)
            symbols = sorted(equation.free_symbols, key=lambda s: s.name)
            if not symbols:                                # pure truth check
                value = sp.simplify(lhs - rhs) == 0
                return value, ("true" if value else "false")
            var = sp.Symbol(var_name) if var_name else symbols[0]
            solutions = [sp.nsimplify(s) for s in sp.solve(equation, var)]
            if len(solutions) == 1:
                return solutions[0], f"{var} = {self._fmt(solutions[0])}"
            pretty = ", ".join(f"{var} = {self._fmt(s)}" for s in solutions)
            return {sp.simplify(s) for s in solutions}, pretty

        expr = sp.nsimplify(sp.simplify(parse_expr(work, transformations=_TRANSFORMS)))
        return expr, self._fmt(expr)

    def _parse_student(self, student: str) -> Any:
        text = re.sub(r"^\s*[a-z]\s*=\s*", "", student.strip(), flags=re.IGNORECASE)
        return sp.nsimplify(sp.simplify(parse_expr(text, transformations=_TRANSFORMS)))

    def _equal(self, expected: Any, student: Any) -> bool:
        if isinstance(expected, set):
            try:
                return sp.simplify(student) in {sp.simplify(e) for e in expected}
            except Exception:  # noqa: BLE001
                return False
        if expected is True or expected is False:
            return bool(expected) == bool(student)
        return sp.simplify(sp.sympify(expected) - sp.sympify(student)) == 0

    @staticmethod
    def _fmt(value: Any) -> str:
        try:
            rational = sp.nsimplify(value)
            if rational.is_Rational and not rational.is_Integer:
                return f"{rational.p}/{rational.q}"
            return str(rational)
        except Exception:  # noqa: BLE001
            return str(value)
