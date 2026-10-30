# Copyright © 2025-2026 Cognizant Technology Solutions Corp, www.cognizant.com.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# END COPYRIGHT

"""Surgical updates for instructions and descriptions in an existing HOCON file."""

import json
import os
import stat
import tempfile
import threading
from pathlib import Path

from pyhocon import ConfigFactory

from middleware.agent_network_consultant.hocon_lexer import HoconLexer
from middleware.agent_network_consultant.hocon_token import HoconToken


class SourcePreservingHoconEditor:
    """Patch supported agent fields without resolving includes or rebuilding the network."""

    # This process-local lock serializes threads without retaining every source path indefinitely. Consultant runs
    # require one writer per target file; coordinating writers across processes belongs at the job-orchestration layer.
    _file_lock = threading.Lock()

    def __init__(
        self,
        changes: dict[str, dict[str, str]],
        original_fields: dict[str, dict[str, str]] | None = None,
    ) -> None:
        """
        Initialize one source-preserving edit operation.

        :param changes: The editable agent fields to update.
        :param original_fields: The resolved field values before Agent Network Consultant changed them.
        """
        self._changes = changes
        self._original_fields = original_fields or {}

    @classmethod
    def update_file(
        cls,
        source_file: str,
        changes: dict[str, dict[str, str]],
        original_fields: dict[str, dict[str, str]] | None = None,
    ) -> str:
        """
        Validate and apply changes atomically, returning the updated HOCON text.

        :param source_file: The source HOCON file path.
        :param changes: The editable agent fields to update.
        :param original_fields: The resolved field values before Agent Network Consultant changed them.
        :return: The resulting text.
        """
        editor = cls(changes, original_fields)
        path = Path(source_file).resolve()
        with cls._file_lock:
            with path.open("r", encoding="utf-8", newline="") as source:
                original = source.read()
            updated = editor._updated_text(original)
            editor._validate_and_atomic_write(path, updated)
            return updated

    @classmethod
    def update_text(
        cls,
        text: str,
        changes: dict[str, dict[str, str]],
        original_fields: dict[str, dict[str, str]] | None = None,
    ) -> str:
        """
        Return HOCON text with only the requested agent fields changed.

        :param text: The HOCON or assertion text to process.
        :param changes: The editable agent fields to update.
        :param original_fields: The resolved field values before Agent Network Consultant changed them.
        :return: The resulting text.
        :raises ValueError: Raised when the requested operation cannot complete.
        """
        return cls(changes, original_fields)._updated_text(text)

    def _updated_text(self, text: str) -> str:
        """
        Apply this operation's requested changes to source text.

        :param text: The HOCON source text to update.
        :return: The updated source text.
        :raises ValueError: If a requested field cannot be edited without changing unrelated source.
        """
        updated = text
        for agent_name, fields in self._changes.items():
            for field_name, new_value in fields.items():
                if field_name not in {"instructions", "description"}:
                    raise ValueError(f"Unsupported agent field for source-preserving edit: {field_name}")
                original_value = self._original_fields.get(agent_name, {}).get(field_name)
                updated = self._replace_agent_field(
                    updated,
                    (agent_name, field_name),
                    new_value,
                    original_value,
                )
        return updated

    def _replace_agent_field(
        self,
        text: str,
        target: tuple[str, str],
        new_value: str,
        original_value: str | None,
    ) -> str:
        """
        Replace one editable field inside a named agent block.

        :param text: The HOCON or assertion text to process.
        :param target: The agent name and editable field name.
        :param new_value: The replacement field value.
        :param original_value: The resolved value before the requested change.
        :return: The resulting text.
        :raises ValueError: Raised when the requested operation cannot complete.
        """
        agent_name, field_name = target
        tokens: list[HoconToken] = HoconLexer(text).tokenize()
        block_start, _ = self._find_agent_block(tokens, agent_name)
        object_start = self._token_index_at(tokens, block_start)
        object_end = self._matching_index(tokens, object_start, "{", "}")
        value_index = self._field_value_index(tokens, (object_start, object_end), agent_name, field_name)
        value_index = self._skip_substitutions(tokens, value_index, object_end)
        if (
            value_index >= object_end
            or tokens[value_index].kind() != "string"
            or self._is_property_key(tokens, value_index, object_end)
        ):
            raise ValueError(f"Could not locate {field_name!r} string for agent {agent_name!r} in source HOCON.")
        token = tokens[value_index]
        literal_value = self._literal_replacement(
            token.value(),
            new_value,
            original_value,
            agent_name,
            field_name,
        )
        replacement = self._format_string_value(literal_value)
        return text[: token.start()] + replacement + text[token.end() :]

    def _field_value_index(
        self,
        tokens: list[HoconToken],
        object_bounds: tuple[int, int],
        agent_name: str,
        field_name: str,
    ) -> int:
        """
        Locate an editable field's value inside one agent object.

        :param tokens: The significant HOCON tokens.
        :param object_bounds: The containing HOCON object's token bounds.
        :param agent_name: The agent or network name to use.
        :param field_name: The editable agent field name.
        :return: The resulting value.
        :raises ValueError: Raised when the requested operation cannot complete.
        """
        object_start, object_end = object_bounds
        if field_name == "instructions":
            return self._property_value_index(tokens, object_start, object_end, field_name)
        function_index = self._property_value_index(tokens, object_start, object_end, "function")
        function_index = self._skip_substitutions(tokens, function_index, object_end)
        if function_index >= object_end or tokens[function_index].value() != "{":
            raise ValueError(f"Could not locate function object for agent {agent_name!r}.")
        function_end = self._matching_index(tokens, function_index, "{", "}")
        return self._property_value_index(tokens, function_index, function_end, "description")

    @staticmethod
    def _literal_replacement(
        source_literal: str,
        new_value: str,
        original_value: str | None,
        agent_name: str,
        field_name: str,
    ) -> str:
        """
        Isolate the changed literal from resolved substitution prefixes and suffixes.

        :param source_literal: The literal string currently present in the source expression.
        :param new_value: The complete resolved field value after the requested change.
        :param original_value: The complete resolved field value before the requested change.
        :param agent_name: The agent or network name being changed.
        :param field_name: The editable field being changed.
        :return: The new source literal, excluding preserved substitution-derived text.
        :raises ValueError: If a composed source value cannot be changed without rewriting its substitutions.
        """
        if original_value is None:
            return new_value
        candidates: list[str] = [source_literal]
        stripped_literal = source_literal.strip()
        if stripped_literal and stripped_literal != source_literal:
            candidates.append(stripped_literal)
        normalized_original = " ".join(original_value.split())
        normalized_literal = " ".join(source_literal.split())
        if original_value == normalized_original and normalized_literal and normalized_literal not in candidates:
            # The shared Designer loader normalizes instruction whitespace before Consultant takes its snapshot.
            # Use that fallback only for normalized snapshots; otherwise the source literal's whitespace is data.
            candidates.append(normalized_literal)
        for candidate in candidates:
            start = original_value.find(candidate)
            if start < 0 or original_value.find(candidate, start + 1) >= 0:
                continue
            end = start + len(candidate)
            prefix = original_value[:start]
            suffix = original_value[end:]
            if not prefix and not suffix:
                return new_value
            if (
                len(new_value) >= len(prefix) + len(suffix)
                and new_value.startswith(prefix)
                and new_value.endswith(suffix)
            ):
                replacement_end = len(new_value) - len(suffix) if suffix else len(new_value)
                return new_value[len(prefix) : replacement_end]
            raise ValueError(
                f"Cannot change substitution-derived text in {field_name!r} for agent {agent_name!r}; "
                "only its source literal can be changed."
            )
        if original_value.strip() != source_literal.strip():
            raise ValueError(f"Could not isolate the source literal for {field_name!r} on agent {agent_name!r}.")
        return new_value

    @staticmethod
    def _format_string_value(value: str) -> str:
        """
        Render a HOCON string value, preferring a triple-quoted block for multi-line text so patched
        instructions/descriptions stay human-readable instead of one escaped line. Falls back to a JSON-quoted
        single line for one-liners or text that itself contains `\"\"\"` (which would break the triple-quote
        delimiter).

        :param value: The value to validate, redact, or return.
        :return: The resulting text.
        """
        if "\n" in value and '"""' not in value:
            return f'"""{value}"""'
        return json.dumps(value, ensure_ascii=False)

    def _find_agent_block(self, tokens: list[HoconToken], agent_name: str) -> tuple[int, int]:
        """
        Return token indexes bounding the requested agent definition.

        :param tokens: The significant HOCON tokens.
        :param agent_name: The agent or network name to use.
        :return: The resulting values.
        :raises ValueError: Raised when the requested operation cannot complete.
        """
        matches: list[tuple[int, int]] = []
        tools_indexes = self._root_property_value_indexes(tokens, "tools")
        for tools_index in tools_indexes:
            tools_index = self._skip_substitutions(tokens, tools_index, len(tokens))
            if tools_index >= len(tokens) or tokens[tools_index].value() != "[":
                continue
            tools_end = self._matching_index(tokens, tools_index, "[", "]")
            index = tools_index + 1
            while index < tools_end:
                if tokens[index].value() == "{":
                    agent_end = self._matching_index(tokens, index, "{", "}")
                    try:
                        name_index = self._property_value_index(tokens, index, agent_end, "name")
                    except ValueError:
                        index = agent_end + 1
                        continue
                    name_index = self._skip_substitutions(tokens, name_index, agent_end)
                    if name_index < agent_end and tokens[name_index].kind() in {"string", "bare"}:
                        if tokens[name_index].value() == agent_name:
                            matches.append((tokens[index].start(), tokens[agent_end].end()))
                    index = agent_end + 1
                    continue
                index += 1

        if not matches:
            raise ValueError(
                f"Could not locate agent {agent_name!r} in the effective directly declared root tools arrays; "
                "the agent may be absent, supplied only through an include, or removed by a later tools assignment."
            )
        if len(matches) > 1:
            raise ValueError(f"Agent name {agent_name!r} is duplicated in the root tools array.")
        return matches[0]

    @staticmethod
    def _token_index_at(tokens: list[HoconToken], start: int) -> int:
        """
        Return the index of the token beginning at a source offset.

        :param tokens: The significant HOCON tokens.
        :param start: The inclusive token-search boundary.
        :return: The resulting value.
        :raises ValueError: Raised when the requested operation cannot complete.
        """
        for index, token in enumerate(tokens):
            if token.start() == start:
                return index
        raise ValueError("Could not resolve HOCON token boundary.")

    def _root_property_value_indexes(self, tokens: list[HoconToken], key: str) -> list[int]:
        """
        Return every direct root value for a key, including ``+=`` fragments.

        :param tokens: The significant HOCON tokens.
        :param key: The HOCON property key to locate.
        :return: The direct root value-token indexes in source order.
        """
        if not tokens:
            return []
        if tokens[0].value() == "{":
            root_end = self._matching_index(tokens, 0, "{", "}")
            return self._effective_property_value_indexes(tokens, 0, root_end, key)
        return self._effective_property_value_indexes(tokens, -1, len(tokens), key)

    @staticmethod
    def _effective_property_value_indexes(tokens: list[HoconToken], start: int, end: int, key: str) -> list[int]:
        """
        Return value indexes that contribute to a direct property's effective HOCON value.

        A plain assignment replaces earlier values, while ``+=`` extends the value established by the most recent
        assignment. Tracking that distinction prevents edits to an overridden root ``tools`` array.

        :param tokens: The significant HOCON tokens.
        :param start: The inclusive token-search boundary, or ``-1`` for an implicit root.
        :param end: The exclusive token-search boundary.
        :param key: The HOCON property key to locate.
        :return: The effective value-token indexes in source order.
        """
        indexes: list[int] = []
        depth = 0
        index = start + 1
        while index < end:
            token = tokens[index]
            if token.value() in {"{", "["}:
                depth += 1
            elif token.value() in {"}", "]"}:
                depth -= 1
            elif depth == 0 and token.kind() in {"string", "bare"} and token.value() == key:
                separator = index + 1
                if separator < end and tokens[separator].value() in {":", "="}:
                    indexes = [separator + 1]
                elif separator < end and tokens[separator].value() == "{":
                    indexes = [separator]
                elif separator + 1 < end and tokens[separator].value() == "+" and tokens[separator + 1].value() == "=":
                    indexes.append(separator + 2)
            index += 1
        return indexes

    @staticmethod
    def _skip_substitutions(tokens: list[HoconToken], index: int, end: int) -> int:
        """
        Advance beyond substitutions that precede a literal field value.

        :param tokens: The significant HOCON tokens.
        :param index: The token or text offset to inspect.
        :param end: The exclusive token-search boundary.
        :return: The resulting value.
        """
        while index < end and tokens[index].kind() == "substitution":
            index += 1
        return index

    @staticmethod
    def _is_property_key(tokens: list[HoconToken], index: int, end: int) -> bool:
        """
        Return whether a candidate string token begins another direct property.

        This prevents a substitution-only editable value from consuming the following quoted property name as its
        replacement literal after substitutions are skipped.

        :param tokens: The significant HOCON tokens.
        :param index: The candidate property-key token index.
        :param end: The exclusive containing-object token boundary.
        :return: Whether the token is followed by a HOCON property separator.
        """
        separator = index + 1
        if separator >= end:
            return False
        if tokens[separator].value() in {":", "=", "{"}:
            return True
        return separator + 1 < end and tokens[separator].value() == "+" and tokens[separator + 1].value() == "="

    def _property_value_index(self, tokens: list[HoconToken], start: int, end: int, key: str) -> int:
        """
        Return the value-token index for a direct property in a bounded block.

        :param tokens: The significant HOCON tokens.
        :param start: The inclusive token-search boundary.
        :param end: The exclusive token-search boundary.
        :param key: The HOCON property key to locate.
        :return: The resulting value.
        :raises ValueError: Raised when the requested operation cannot complete.
        """
        indexes = self._property_value_indexes(tokens, start, end, key)
        if len(indexes) == 1:
            return indexes[0]
        if len(indexes) > 1:
            raise ValueError(f"Direct property {key!r} is duplicated in HOCON object.")
        raise ValueError(f"Could not locate direct property {key!r} in HOCON object.")

    @staticmethod
    def _property_value_indexes(tokens: list[HoconToken], start: int, end: int, key: str) -> list[int]:
        """
        Return every value-token index for a direct property in a bounded block.

        :param tokens: The significant HOCON tokens.
        :param start: The inclusive token-search boundary, or ``-1`` for an implicit root.
        :param end: The exclusive token-search boundary.
        :param key: The HOCON property key to locate.
        :return: The matching value-token indexes in source order.
        """
        indexes: list[int] = []
        depth = 0
        index = start + 1
        while index < end:
            token = tokens[index]
            if token.value() in {"{", "["}:
                depth += 1
            elif token.value() in {"}", "]"}:
                depth -= 1
            elif depth == 0 and token.kind() in {"string", "bare"} and token.value() == key:
                separator = index + 1
                if separator < end and tokens[separator].value() in {":", "="}:
                    indexes.append(separator + 1)
                elif separator < end and tokens[separator].value() == "{":
                    # HOCON permits object-valued properties without ``=`` or ``:``, as in ``function { ... }``.
                    indexes.append(separator)
                elif separator + 1 < end and tokens[separator].value() == "+" and tokens[separator + 1].value() == "=":
                    indexes.append(separator + 2)
            index += 1
        return indexes

    @staticmethod
    def _matching_index(tokens: list[HoconToken], start: int, opening: str, closing: str) -> int:
        """
        Return the closing token matching a nested opening token.

        :param tokens: The significant HOCON tokens.
        :param start: The inclusive token-search boundary.
        :param opening: The opening delimiter.
        :param closing: The closing value.
        :return: The resulting value.
        :raises ValueError: Raised when the requested operation cannot complete.
        """
        if tokens[start].value() != opening:
            raise ValueError(f"Expected {opening!r} at HOCON token boundary.")
        depth = 0
        for index in range(start, len(tokens)):
            if tokens[index].value() == opening:
                depth += 1
            elif tokens[index].value() == closing:
                depth -= 1
                if depth == 0:
                    return index
        raise ValueError(f"Unterminated HOCON {opening!r} block.")

    def _validate_and_atomic_write(self, path: Path, content: str) -> None:
        """
        Validate HOCON content and atomically replace its source file.

        :param path: The file or token path to process.
        :param content: The text content to process or persist.
        """
        mode = stat.S_IMODE(path.stat().st_mode)
        temporary_name = ""
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="", suffix=".hocon", dir=path.parent, delete=False
            ) as temporary:
                temporary.write(content)
                temporary_name = temporary.name
            # Syntax-check without resolving substitutions. Resolution depends on the
            # network's include graph and environment and is handled by normal loading.
            ConfigFactory.parse_file(temporary_name, resolve=False)
            os.chmod(temporary_name, mode)
            os.replace(temporary_name, path)
            temporary_name = ""
        finally:
            if temporary_name and os.path.exists(temporary_name):
                os.unlink(temporary_name)
