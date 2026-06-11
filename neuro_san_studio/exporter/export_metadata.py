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

    # Indentation for keys/comment lines inside the metadata block, and for its closing brace.
    _INDENT = "        "
    _CLOSE_INDENT = "    "

    def build(self) -> Dict[str, str]:
        """Assemble the export-provenance keys written into the network's metadata at export time."""
        return {
            "export_user": self._current_user(),
            "export_time": datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%Z"),
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

        region = text[open_brace:end]  # the metadata block, '{' ... '}' inclusive
        region, missing = self._update_existing(region, kv)
        region = self._append_missing(region, missing)
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

    def _append_missing(self, region: str, missing: Dict[str, str]) -> str:
        """Append ``missing`` keys before the block's closing brace, adding the comment once."""
        if not missing:
            return region
        note = "" if self._note_marker() in region else self._render_note()
        keys = "".join(f'{self._INDENT}"{key}": "{self._escape(value)}",\n' for key, value in missing.items())
        close = region.rfind("}")
        # rstrip the head so we don't leave a whitespace-only line between the last existing
        # key and our injected block.
        head = region[:close].rstrip()
        return head + "\n" + note + keys.rstrip("\n") + "\n" + self._CLOSE_INDENT + region[close:]

    def _create_block(self, text: str, kv: Dict[str, str]) -> str:
        """Insert a fresh metadata block (note + keys) just after the document's root brace."""
        keys = "".join(f'{self._INDENT}"{key}": "{self._escape(value)}",\n' for key, value in kv.items())
        block = '\n    "metadata": {\n' + self._render_note() + keys + "    },"
        root = text.index("{")
        return text[: root + 1] + block + text[root + 1 :]

    def _render_note(self) -> str:
        """The comment block (one ``#`` line per note line) at the block's indentation."""
        return "".join(f"{self._INDENT}# {line}\n" for line in self._NOTE_LINES)

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
