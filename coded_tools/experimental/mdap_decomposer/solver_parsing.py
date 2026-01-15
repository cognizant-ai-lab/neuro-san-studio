# Copyright © 2025 Cognizant Technology Solutions Corp, www.cognizant.com.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# END COPYRIGHT

import os
import re


class SolverParsing:
    """
    Parses results for solver.

    This class would probably not be necessary if the agents used by the NeuroSanSolver
    were using the "structure_formats": "json" option.
    """

    # agents end their final answer on the last line after this token
    FINAL_TOKEN: str = os.getenv("FINAL_TOKEN", "vote:")

    _DECOMP_FIELD_RE: re.Pattern = re.compile(r"(P1|P2|C)\s*=\s*\[(.*?)]", re.DOTALL)

    def extract_final(self, text: str, token: str = FINAL_TOKEN) -> str:
        """
        Return the text after the last occurrence of token (case-insensitive),
        or the last non-empty line if not found. Preserves original casing.
        """
        if not text:
            return ""
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not lines:
            return ""
        tkn = (token or "").strip()
        if not tkn:
            return lines[-1]

        tkn_lower = tkn.lower()
        for ln in reversed(lines):
            # Find LAST occurrence of token in this line (case-insensitive)
            idx = ln.lower().rfind(tkn_lower)
            if idx != -1:
                return ln[idx + len(tkn):].strip()
        return lines[-1]

    def extract_decomposition_text(self, resp: str) -> str | None:
        """
        Scan the FULL agent response (multi-line) for P1=[...], P2=[...], C=[...].
        Returns a canonical single-line 'P1=[...], P2=[...], C=[...]' or None.
        """
        fields = {}
        for label, val in self._DECOMP_FIELD_RE.findall(resp or ""):
            fields[label] = val.strip()

        if fields:
            p1 = fields.get("P1", "None")
            p2 = fields.get("P2", "None")
            c = fields.get("C", "None")
            return f"P1=[{p1}], P2=[{p2}], C=[{c}]"

        # Fallback: if the last line already contains the canonical string
        tail = self.extract_final(resp)
        if "P1=" in tail and "C=" in tail:
            return tail
        return None

    def parse_decomposition(self, decomp_line: str) -> tuple[str | None, str | None, str | None]:
        """
        Parses: P1=[p1], P2=[p2], C=[c]
        Returns (p1, p2, c) with 'None' coerced to None.
        """
        parts = {
            seg.split("=", 1)[0].strip(): seg.split("=", 1)[1].strip() for seg in decomp_line.split(",") if "=" in seg
        }

        p1 = self.unbracket(parts.get("P1"))
        p2 = self.unbracket(parts.get("P2"))
        c = self.unbracket(parts.get("C"))
        return p1, p2, c

    def unbracket(self, s: str | None) -> str | None:
        if not s:
            return None
        s = s.strip()
        if s.startswith("[") and s.endswith("]"):
            s = s[1:-1].strip()
        return None if s == "None" else s
