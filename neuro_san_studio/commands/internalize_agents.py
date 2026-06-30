# Copyright © 2025-2026 Cognizant Technology Solutions Corp, www.cognizant.com.
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

"""Implementation of the `neuro-san-studio internalize-agents` command.

Reads an agent network HOCON file that calls other agent networks via
`/`-prefixed external-agent references, loads those external HOCON files,
and writes a single self-contained HOCON where the referenced networks
become internal agents.

Workaround for load-test failures where the server's loopback HTTP fetch of
an external agent's function spec times out under concurrent load and the
tool is silently dropped from the LLM's tools array. After internalizing,
the agents live in the same HOCON and need no loopback.

The output is fully resolved: all `include` statements and `${...}`
substitutions in the input (and every transitively-loaded external) are
applied by the parser, and the result is written as HOCON using a JSON-like
style (quoted keys + commas), with HOCON triple-quoted blocks for multi-line strings.
"""

import json
import sys
from pathlib import Path
from typing import Any
from typing import Iterable

from neuro_san.internals.persistence.abstract_async_config_restorer import AbstractAsyncConfigRestorer

# Exit codes. neuro-san-studio's main() treats code 2 as a clean "help" exit,
# so we normalize to a binary contract: 0 = ok, 1 = problem.
EXIT_OK = 0
EXIT_ERROR = 1

# Default colon-separated list of directories to search for external <name>.hocon files.
# Only `registries` is needed because subdirectories (e.g., `/industry/banking_ops`) are
# expressed in the reference name itself, not by adding more entries here.
DEFAULT_SEARCH_PATHS: str = "registries"

# Output formatting. Indent matches the style of the source hocon files; the line budget
# is a soft target -- string values with embedded newlines are emitted as HOCON
# triple-quoted strings (one logical line per real newline), but long single-line strings
# without internal newlines can still exceed it.
OUTPUT_INDENT: int = 4
OUTPUT_LINE_BUDGET: int = 120


class InternalizeAgentsCommand:
    """Internalize external agent references in an agent network HOCON file.

    Recursively inlines `/`-prefixed external-agent references into a single self-contained
    HOCON. See module docstring for the workaround context.
    """

    def __init__(
        self,
        input_path: str,
        output_path: str,
        *,
        search_paths: str | None = None,
    ):
        """Initialize the command.

        Args:
            input_path: Path to the parent HOCON file.
            output_path: Path to write the combined HOCON.
            search_paths: Colon-separated directories to search for external HOCON files.
                Each `/<ref>` reference is joined as `<search_path>/<ref>.hocon`, so refs
                that contain `/` (e.g. `/industry/banking_ops`) traverse subdirectories
                under each search path naturally. Defaults to "registries".
        """
        self.input_path: Path = Path(input_path)
        self.output_path: Path = Path(output_path)
        raw_search_paths: str = search_paths or DEFAULT_SEARCH_PATHS
        self.search_paths: list[Path] = [Path(p) for p in raw_search_paths.split(":") if p]

    def run(self) -> int:
        """Build the combined config and write it. Return 0 on success, 1 on failure."""
        if not self.input_path.is_file():
            print(f"Error: input not found: {self.input_path}", file=sys.stderr)
            return EXIT_ERROR
        try:
            combined = self.build_combined_config(self.input_path, self.search_paths)
            output_text: str = self.render_hocon(combined)
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            self.output_path.write_text(output_text, encoding="utf-8")
        except Exception as exception:  # pylint: disable=broad-except
            print(f"Error: Could not internalize '{self.input_path}' - {exception}", file=sys.stderr)
            return EXIT_ERROR
        n_agents = len(combined.get("tools", []))
        print(f"Wrote {self.output_path} ({n_agents} agents included).")
        return EXIT_OK

    # ---- HOCON parsing and recursive inlining ----

    @staticmethod
    def parse_hocon(path: Path) -> dict[str, Any]:
        """Parse a HOCON (or JSON) file via neuro-san's AbstractAsyncConfigRestorer so that
        includes and substitutions resolve identically to the server. The script must run from
        a cwd where the includes resolve (typically the repo root).
        """
        return AbstractAsyncConfigRestorer(file_purpose="agent network hocon").restore(file_reference=str(path))

    @staticmethod
    def find_external_hocon(name: str, search_paths: Iterable[Path]) -> Path:
        """Locate <name>.hocon on one of the search paths.

        Validates that `name` cannot escape the search base. Without this guard, a ref like
        `/etc/passwd` (absolute) or `../../secrets` (parent traversal) would be joined into a
        path that reads files outside the intended scope -- and since internalize-agents embeds
        the loaded file's contents into the output, the leak would propagate to whoever reads
        the generated hocon.
        """
        ref = Path(name)
        if ref.is_absolute() or ref.drive or ".." in ref.parts:
            raise ValueError(f"Invalid external agent reference: {name!r}")
        tried: list[Path] = []
        for base in search_paths:
            candidate = base / f"{name}.hocon"
            tried.append(candidate)
            if candidate.is_file():
                return candidate
        raise FileNotFoundError(
            f"Could not find {name}.hocon in any search path. Tried: " + ", ".join(str(p) for p in tried)
        )

    @staticmethod
    def collect_external_refs(node: Any, refs: set[str]) -> None:
        """Walk a parsed config recursively; collect any string of the form `/<name>`."""
        if isinstance(node, str):
            # External agent refs start with `/` followed by the network name.
            # Plain `/` or empty-name refs are not valid; skip them.
            if node.startswith("/") and len(node) > 1:
                refs.add(node[1:])
        elif isinstance(node, dict):
            for value in node.values():
                InternalizeAgentsCommand.collect_external_refs(value, refs)
        elif isinstance(node, list):
            for item in node:
                InternalizeAgentsCommand.collect_external_refs(item, refs)

    @staticmethod
    def strip_inlined_refs(node: Any, ref_to_frontman: dict[str, str]) -> Any:
        """Return a deep copy of `node` with each `/<ref>` string replaced by the front_man name
        of the external network it points to. Critically, the file STEM (used in the reference)
        can differ from the front_man name (e.g., `/agent_network_editor` -> `network_editor`).
        """
        if isinstance(node, str):
            if node.startswith("/") and node[1:] in ref_to_frontman:
                return ref_to_frontman[node[1:]]
            return node
        if isinstance(node, dict):
            return {
                key: InternalizeAgentsCommand.strip_inlined_refs(value, ref_to_frontman) for key, value in node.items()
            }
        if isinstance(node, list):
            return [InternalizeAgentsCommand.strip_inlined_refs(item, ref_to_frontman) for item in node]
        return node

    @staticmethod
    def clean_inlined_agents(agents: list[dict[str, Any]]) -> None:
        """Strip fields that only make sense when agents are referenced as external networks.

        After internalizing, the only agent that is still externally callable is the front_man
        (index 0). All other agents are internal, so:
          - `allow` (sly_data routing to/from external agents) is dropped entirely.
          - `structure_formats` (front-man-only) is dropped.

        On the front_man itself, `allow` is trimmed to keep only the keys whose semantics still
        apply once there are no downstream external agents:
          - `to_upstream`  -- data flowing out to whoever calls this network.
          - `to_tracing`   -- data flowing out to an observability backend.
        The `from_downstream` and `to_downstream` keys are dropped because there are no
        downstream external agents anymore.
        """
        front_man_allow_keys: set[str] = {"to_upstream", "to_tracing"}
        for index, agent in enumerate(agents):
            if not isinstance(agent, dict):
                continue
            is_front_man: bool = index == 0
            if is_front_man:
                allow = agent.get("allow")
                if isinstance(allow, dict):
                    trimmed = {key: value for key, value in allow.items() if key in front_man_allow_keys}
                    if trimmed:
                        agent["allow"] = trimmed
                    else:
                        agent.pop("allow", None)
            else:
                agent.pop("allow", None)
                agent.pop("structure_formats", None)

    @staticmethod
    def collect_external_refs_in_agents(agents: list[dict[str, Any]]) -> set[str]:
        """Collect every `/<name>` external ref appearing in any agent's `tools`, `messages`,
        or `allow` field. Other fields are ignored because external-agent references don't
        legitimately appear elsewhere.
        """
        refs: set[str] = set()
        for agent in agents:
            if isinstance(agent, dict):
                InternalizeAgentsCommand.collect_external_refs(agent.get("tools"), refs)
                InternalizeAgentsCommand.collect_external_refs(agent.get("messages"), refs)
                InternalizeAgentsCommand.collect_external_refs(agent.get("allow"), refs)
        return refs

    @staticmethod
    def merge_external_agents(
        target: list[dict[str, Any]],
        source: list[dict[str, Any]],
        names_in_target: set[str],
    ) -> None:
        """Append each agent from `source` into `target` unless an agent with the same `name` is
        already present. Mutates both `target` (appended) and `names_in_target` (updated).
        """
        for agent in source:
            if not isinstance(agent, dict):
                continue
            name = agent.get("name")
            if not name or name in names_in_target:
                continue
            target.append(agent)
            names_in_target.add(name)

    @staticmethod
    def internalize_externals(
        hocon_path: Path,
        search_paths: list[Path],
        visited: set[Path],
        ref_to_frontman: dict[str, str],
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Recursively parse `hocon_path` and return its inlined agent list and own front_man name.

        Mutates `ref_to_frontman` to record `external_ref_name -> front_man_name` for every external
        network reached during recursion. This mapping is later used to rewrite `/ref` strings in
        the final config, since the file stem (used in the reference) can differ from the front_man
        name (e.g., `agent_network_editor.hocon` has front_man `network_editor`).

        Circular external references are detected via `visited`.
        """
        cls = InternalizeAgentsCommand
        resolved = hocon_path.resolve()
        if resolved in visited:
            raise RuntimeError(f"Circular external reference detected: {resolved} (already on resolution stack)")
        visited.add(resolved)
        try:
            # Top-level `tools` is the list of agents in a neuro-san network.
            agents: list[dict[str, Any]] = list(cls.parse_hocon(hocon_path).get("tools", []))
            # By convention the first agent in `tools` is the front_man (the externally-callable one).
            own_front_man: str | None = agents[0].get("name") if agents and isinstance(agents[0], dict) else None
            own_names: set[str] = {a.get("name") for a in agents if isinstance(a, dict) and a.get("name")}
            # An external network may reference one of its own agents with a leading slash by mistake;
            # treat anything already in own_names as not external.
            external_refs: set[str] = cls.collect_external_refs_in_agents(agents) - own_names

            # Process external refs in sorted order for deterministic output.
            for ext_name in sorted(external_refs):
                if ext_name in ref_to_frontman:
                    # Already inlined elsewhere in the recursion; skip re-parsing.
                    continue
                ext_path = cls.find_external_hocon(ext_name, search_paths)
                ext_agents, ext_front_man = cls.internalize_externals(ext_path, search_paths, visited, ref_to_frontman)
                # Record the mapping so `/ext_name` can be rewritten to the actual front_man name.
                # Fall back to ext_name itself if the external file had no front_man we could find.
                ref_to_frontman[ext_name] = ext_front_man if ext_front_man else ext_name
                cls.merge_external_agents(agents, ext_agents, own_names)

            return agents, own_front_man
        finally:
            visited.discard(resolved)

    @staticmethod
    def build_combined_config(input_path: Path, search_paths: list[Path]) -> dict[str, Any]:
        """Build the fully-resolved combined config dict with externals inlined into the top-level
        `tools` list. All `include` statements and `${...}` substitutions in the input (and in
        every transitively-loaded external) have already been resolved by the parser, so the
        returned dict is self-contained.
        """
        cls = InternalizeAgentsCommand
        combined: dict[str, Any] = cls.parse_hocon(input_path)
        ref_to_frontman: dict[str, str] = {}
        agents, _ = cls.internalize_externals(input_path, search_paths, visited=set(), ref_to_frontman=ref_to_frontman)
        # Apply the full mapping once to every agent (parent + all transitively-inlined externals).
        agents = [cls.strip_inlined_refs(agent, ref_to_frontman) for agent in agents]
        cls.clean_inlined_agents(agents)
        combined["tools"] = agents
        return combined

    # ---- Output rendering helpers ----

    @staticmethod
    def format_scalar(value: Any) -> str:
        """Render a non-collection value (None, bool, int, float, str) as HOCON text."""
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return json.dumps(value)
        if isinstance(value, str):
            # Strings with embedded newlines become HOCON triple-quoted (newlines preserved
            # literally). Strings containing the `"""` sequence fall back to JSON escaping --
            # there's no clean way to embed a literal `"""` inside a triple-quoted HOCON string.
            if "\n" in value and '"""' not in value:
                return f'"""\n{value}"""' if value.endswith("\n") else f'"""\n{value}\n"""'
            return json.dumps(value, ensure_ascii=False)
        # Fallback for anything unexpected; keeps the output valid JSON.
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def format_value(value: Any, current_indent: int) -> str:
        """Render any value (scalar or collection) at the given indentation level."""
        cls = InternalizeAgentsCommand
        if isinstance(value, dict):
            return cls.format_dict(value, current_indent)
        if isinstance(value, list):
            return cls.format_list(value, current_indent)
        return cls.format_scalar(value)

    @staticmethod
    def format_dict(node: dict[str, Any], current_indent: int) -> str:
        """Render an object on multiple lines with one key per line."""
        cls = InternalizeAgentsCommand
        if not node:
            return "{}"
        inner_indent: int = current_indent + OUTPUT_INDENT
        pad: str = " " * inner_indent
        end_pad: str = " " * current_indent
        items = list(node.items())
        lines: list[str] = ["{"]
        for i, (key, value) in enumerate(items):
            rendered = cls.format_value(value, inner_indent)
            comma = "," if i < len(items) - 1 else ""
            lines.append(f"{pad}{json.dumps(key)}: {rendered}{comma}")
        lines.append(f"{end_pad}}}")
        return "\n".join(lines)

    @staticmethod
    def format_list(node: list[Any], current_indent: int) -> str:
        """Render an array. Inline short scalar-only arrays; otherwise one item per line."""
        cls = InternalizeAgentsCommand
        if not node:
            return "[]"
        # Try inline form for arrays of simple values (strings, numbers, bools, None) if it fits.
        if all(not isinstance(item, (dict, list)) for item in node):
            inline = "[" + ", ".join(cls.format_scalar(item) for item in node) + "]"
            if "\n" not in inline and current_indent + len(inline) <= OUTPUT_LINE_BUDGET:
                return inline
        inner_indent: int = current_indent + OUTPUT_INDENT
        pad: str = " " * inner_indent
        end_pad: str = " " * current_indent
        lines: list[str] = ["["]
        for i, item in enumerate(node):
            rendered = cls.format_value(item, inner_indent)
            comma = "," if i < len(node) - 1 else ""
            lines.append(f"{pad}{rendered}{comma}")
        lines.append(f"{end_pad}]")
        return "\n".join(lines)

    @staticmethod
    def render_hocon(combined: dict[str, Any]) -> str:
        """Render the combined config as HOCON text with 4-space indent."""
        return InternalizeAgentsCommand.format_dict(combined, current_indent=0) + "\n"
