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

import getpass
import re
from datetime import datetime
from typing import Dict
from typing import Tuple

from neuro_san_studio.utils.hocon_text import HoconText
from neuro_san_studio.utils.version import studio_version


class ExportMetadataStamper:
    """Stamp export provenance (user, time, studio version) into a network's metadata block.

    Idempotent: stamping an already-stamped network refreshes the existing values in place
    rather than appending a second set, so re-exporting only updates the user/time/version.
    """

    # Matches the first top-level ``metadata`` key and its opening brace, tolerating
    # quoted/unquoted keys and ``:`` / ``=`` / bare-object HOCON separators.
    _METADATA_RE = re.compile(r"""(["']?)metadata\1\s*[:=]?\s*\{""")

    # HOCON comment lines describing the stamped keys, injected just above them on first stamp.
    # One entry per line; rendered with a leading '#' and the block's indentation.
    _NOTE_LINES = (
        "ns export metadata",
        "export_user: system user who ran the export",
        "export_time: YYYYMMDD-hhmmss-TZ in the local timezone",
        "export_neuro_san_studio_version: studio version at export time",
    )

    # One indentation level (HOCON convention). Keys sit one level deeper than the
    # ``metadata`` line; the closing brace lines up with it.
    _LEVEL = "    "

    def build(self) -> Dict[str, str]:
        """Assemble the export-provenance keys written into the network's metadata at export time."""
        now = datetime.now().astimezone()
        tz = now.strftime("%Z") or now.strftime("%z") or "local"
        return {
            "export_user": self._current_user(),
            "export_time": now.strftime("%Y%m%d-%H%M%S-") + tz,
            "export_neuro_san_studio_version": studio_version(),
        }

    def stamp(self, text: str) -> str:
        """Return ``text`` with the export-provenance keys set in its top-level metadata block.

        Keys already present (from a previous export) are updated in place; missing keys are
        appended. A metadata block is created just after the root brace if the network has none.
        Purely textual, so includes, substitutions, and comments elsewhere are left untouched.
        """
        kv = self.build()
        match = self._METADATA_RE.search(text)
        if not match:
            return self._create_block(text, kv)

        open_brace = text.index("{", match.start())
        end = HoconText.match_closing_brace(text, open_brace)
        if end is None:
            raise ValueError("Unbalanced braces: no closing brace for metadata block.")

        # Keys sit one level in from the ``metadata`` line itself, so the indent adapts whether
        # ``metadata`` is at column 0 or nested. Detected from the line, not from the brace.
        key_indent = self._line_indent(text, match.start()) + self._LEVEL

        region = text[open_brace:end]  # the metadata block, '{' ... '}' inclusive
        region, missing = self._update_existing(region, kv)
        region = self._append_missing(region, missing, key_indent)
        return text[:open_brace] + region + text[end:]

    def _update_existing(self, region: str, kv: Dict[str, str]) -> Tuple[str, Dict[str, str]]:
        """Replace any export keys already present in ``region`` with their new values.

        Returns the updated region and the subset of ``kv`` that wasn't found (to be appended).
        """
        missing: Dict[str, str] = {}
        for key, value in kv.items():
            # Match `"key" : "<old value>"` and swap only the value, keeping the original spacing.
            pattern = re.compile(r'("' + re.escape(key) + r'"\s*[:=]\s*)"(?:\\.|[^"\\])*"')
            region, count = pattern.subn(lambda m, v=value: m.group(1) + f'"{self._escape(v)}"', region, count=1)
            if not count:
                missing[key] = value
        return region, missing

    def _append_missing(self, region: str, missing: Dict[str, str], key_indent: str) -> str:
        """Insert ``missing`` keys (and the comment, once) before the block's closing brace."""
        if not missing:
            return region
        note = "" if self._note_marker() in region else self._render_note(key_indent)
        keys = "".join(f'{key_indent}"{key}": "{self._escape(value)}",\n' for key, value in missing.items())
        close = region.rfind("}")
        # Drop trailing whitespace before the brace so we don't leave a blank line; the closing
        # brace line (region[close:]) is preserved verbatim.
        head = region[:close].rstrip()
        brace_indent = region[region.rfind("\n", 0, close) + 1 : close]
        return head + "\n" + note + keys + brace_indent + region[close:]

    def _create_block(self, text: str, kv: Dict[str, str]) -> str:
        """Insert a fresh metadata block for a network that has none.

        If the document has a root ``{ ... }``, the block goes just inside it. For a brace-less
        document (top-level ``key = ...`` statements), the block is prepended as a sibling
        top-level key, after any leading comments/includes.
        """
        start = HoconText.first_significant_index(text)
        if start < len(text) and text[start] == "{":
            meta_indent = self._LEVEL
            key_indent = meta_indent + self._LEVEL
            keys = "".join(f'{key_indent}"{key}": "{self._escape(value)}",\n' for key, value in kv.items())
            block = f'\n{meta_indent}"metadata": {{\n' + self._render_note(key_indent) + keys + f"{meta_indent}}},"
            return text[: start + 1] + block + text[start + 1 :]

        # Brace-less root: prepend metadata as its own top-level key (indented one level).
        key_indent = self._LEVEL
        keys = "".join(f'{key_indent}"{key}": "{self._escape(value)}",\n' for key, value in kv.items())
        block = '"metadata": {\n' + self._render_note(key_indent) + keys + "}\n"
        return text[:start] + block + text[start:]

    @staticmethod
    def _line_indent(text: str, pos: int) -> str:
        """Leading whitespace of the line containing ``pos`` (used to indent relative to it)."""
        line_start = text.rfind("\n", 0, pos) + 1
        return text[line_start : pos - len(text[line_start:pos].lstrip())]

    def _render_note(self, indent: str) -> str:
        """The comment block (one ``#`` line per note line) at ``indent``."""
        return "".join(f"{indent}# {line}\n" for line in self._NOTE_LINES)

    def _note_marker(self) -> str:
        """First note line as it appears in text; its presence means the comment is already there."""
        return f"# {self._NOTE_LINES[0]}"

    @staticmethod
    def _escape(value: str) -> str:
        """Escape a value for embedding in a double-quoted HOCON string."""
        return value.replace("\\", "\\\\").replace('"', '\\"')

    @staticmethod
    def _current_user() -> str:
        """System user, or 'unknown' if the environment has no resolvable user."""
        try:
            return getpass.getuser()
        except (OSError, KeyError):
            return "unknown"
