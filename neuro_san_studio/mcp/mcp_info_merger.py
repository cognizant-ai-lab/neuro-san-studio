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

"""Filter and merge ``mcp_info.hocon`` files at the URL-block level.

``mcp_info.hocon`` is a dict mapping MCP server URLs to per-server config (``http_headers``,
``tools``). The values often contain ``${ENV_VAR}`` substitutions and inline comments that
don't round-trip cleanly through pyhocon — re-emitting parsed config would lose the env-var
references. So this module operates on the source text directly, slicing each ``"url": { ... }``
block out verbatim (brace-counted, comment-aware) so env vars and formatting survive both the
filter step on export and the merge step on import.
"""

from collections import OrderedDict
from pathlib import Path
from typing import Dict
from typing import Iterable
from typing import List
from typing import Optional
from typing import Tuple

from neuro_san_studio.utils.hocon_text import HoconText


class McpInfoMerger:
    """Parse, filter, render, and merge ``mcp_info.hocon`` text at the URL-block level.

    All operations work on raw HOCON source text rather than a parsed model so that
    ``${ENV_VAR}`` substitutions and inline comments are preserved verbatim across the
    export filter step and the import merge step.
    """

    _COPYRIGHT_FILE = Path(__file__).resolve().parents[2] / "build_scripts" / "source_available_copyright.txt"

    def extract_blocks(self, text: str) -> "OrderedDict[str, str]":
        """Return ``{url: verbatim_block_text}`` for every ``"url": { ... }`` entry at the top level.

        Walks the source character by character so that inline comments, env-var references
        (``${ENV}``), and nested braces inside string values are all handled correctly. Skips
        URL tokens that appear after a ``#`` on the same line — those are commented-out examples.
        """
        blocks: "OrderedDict[str, str]" = OrderedDict()
        n = len(text)
        i = 0
        while i < n:
            if text[i] == "#":
                i = HoconText.skip_line(text, i)
                continue
            if text[i] == '"':
                url_end = HoconText.find_string_end(text, i)
                if url_end == -1:
                    break
                token = text[i + 1 : url_end]
                if token.startswith(("http://", "https://")) and not self._line_is_commented(text, i):
                    block_end = self._try_parse_block(text, url_end)
                    if block_end is not None:
                        blocks[token] = text[i:block_end].rstrip(" \t")
                        i = self._consume_trailing_comma(text, block_end)
                        continue
                i = url_end + 1
                continue
            i += 1
        return blocks

    def filter_blocks(self, source_text: str, wanted_urls: Iterable[str]) -> "OrderedDict[str, str]":
        """Return only the blocks whose URL appears in ``wanted_urls`` (preserving source order)."""
        wanted = set(wanted_urls)
        return OrderedDict((url, block) for url, block in self.extract_blocks(source_text).items() if url in wanted)

    def render_file(self, blocks: Dict[str, str]) -> str:
        """Render an ``mcp_info.hocon`` containing exactly ``blocks`` (preserves the per-block text verbatim)."""
        header = self._license_header()
        if not blocks:
            return header + "\n{\n}\n"
        rendered_blocks = ",\n\n".join(self._indent_block(block) for block in blocks.values())
        return header + "\n{\n" + rendered_blocks + "\n}\n"

    def merge(self, receiver_text: str, additions: Dict[str, str]) -> Tuple[str, List[str], List[str]]:
        """Add any URL blocks from ``additions`` that aren't already present in ``receiver_text``.

        Returns ``(new_text, added_urls, skipped_urls)``. Existing URLs are never overwritten —
        that's the additive contract: an import never replaces a server config the receiver
        already configured (e.g. with their own ``${ENV}`` setup). Skipped entries surface in
        the return so callers can warn.
        """
        if not additions:
            return receiver_text, [], []

        existing_urls = set(self.extract_blocks(receiver_text).keys())
        added: List[str] = []
        skipped: List[str] = []
        new_blocks: List[str] = []
        for url, block in additions.items():
            if url in existing_urls:
                skipped.append(url)
            else:
                added.append(url)
                new_blocks.append(block)

        if not new_blocks:
            return receiver_text, added, skipped

        if not self._has_outer_dict(receiver_text):
            # No outer ``{}`` yet — wrap the additions in one and emit a fresh-shaped file.
            return self.render_file(OrderedDict(zip(added, new_blocks))), added, skipped

        return self._splice_blocks_before_close(receiver_text, new_blocks), added, skipped

    # --- internals ---------------------------------------------------------------------------------

    @classmethod
    def _license_header(cls) -> str:
        """Read the project's standard copyright header verbatim from ``build_scripts/``.

        Reading from the source-of-truth file keeps a single canonical license blob across the
        repo; an inlined copy would silently drift the day someone updates the master.
        """
        text = cls._COPYRIGHT_FILE.read_text(encoding="utf-8")
        return text if text.endswith("\n") else text + "\n"

    @staticmethod
    def _line_is_commented(text: str, pos: int) -> bool:
        """True iff a ``#`` precedes ``pos`` on the same line (i.e. this token is inside a comment)."""
        line_start = text.rfind("\n", 0, pos) + 1
        return "#" in text[line_start:pos]

    @staticmethod
    def _try_parse_block(text: str, key_end: int) -> Optional[int]:
        """If the quoted key ending at ``key_end`` is followed by ``[: or =] {...}``, return the index
        just past the closing ``}``. Otherwise return None — the quoted token wasn't an entry header."""
        n = len(text)
        j = key_end + 1
        while j < n and text[j] in " \t\r\n":
            j += 1
        if j >= n or text[j] not in (":", "="):
            return None
        j += 1
        while j < n and text[j] in " \t\r\n":
            j += 1
        if j >= n or text[j] != "{":
            return None
        return HoconText.match_closing_brace(text, j)

    @staticmethod
    def _consume_trailing_comma(text: str, pos: int) -> int:
        """Advance past whitespace + an optional comma after a block, so the walker doesn't re-enter it."""
        n = len(text)
        j = pos
        while j < n and text[j] in " \t":
            j += 1
        if j < n and text[j] == ",":
            return j + 1
        return pos

    @classmethod
    def _has_outer_dict(cls, text: str) -> bool:
        """Heuristic: does the file already have an outer ``{ ... }`` we can splice into?"""
        stripped = cls._strip_comments(text).strip()
        return stripped.startswith("{") and stripped.endswith("}")

    @staticmethod
    def _strip_comments(text: str) -> str:
        """Drop ``#``-prefixed lines so ``_has_outer_dict`` doesn't get fooled by leading comments."""
        out: List[str] = []
        for line in text.splitlines():
            idx = line.find("#")
            if idx == -1:
                out.append(line)
            else:
                out.append(line[:idx])
        return "\n".join(out)

    @staticmethod
    def _indent_block(block: str) -> str:
        """Indent every line of a block by four spaces so it sits cleanly inside the outer dict."""
        return "\n".join(("    " + line if line else line) for line in block.splitlines())

    def _splice_blocks_before_close(self, receiver_text: str, new_blocks: List[str]) -> str:
        """Insert ``new_blocks`` before the final ``}`` of ``receiver_text``, preserving everything else.

        Adds a leading comma if the existing content needs one (i.e. the last meaningful char before
        ``}`` isn't already ``,`` or ``{``), so the resulting HOCON is still well-formed.
        """
        last_brace = receiver_text.rfind("}")
        if last_brace == -1:
            return receiver_text + "\n" + "\n".join(self._indent_block(b) for b in new_blocks) + "\n"

        head = receiver_text[:last_brace].rstrip()
        tail = receiver_text[last_brace:]

        last_char = head.rstrip().rstrip("\n").rstrip()[-1:] if head.strip() else ""
        needs_comma = last_char not in ("", ",", "{")
        sep = ",\n\n" if needs_comma else "\n\n"
        indented = ",\n\n".join(self._indent_block(b) for b in new_blocks)

        return head + sep + indented + "\n" + tail
