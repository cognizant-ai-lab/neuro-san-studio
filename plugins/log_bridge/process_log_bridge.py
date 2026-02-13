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
from __future__ import annotations

import copy
import json
import logging
import re
import threading
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional, TextIO, Tuple

from rich.console import Console
from rich.logging import RichHandler
from rich.syntax import Syntax
from rich.text import Text
from rich.theme import Theme


log_cfg = {
    # Refer rich guidelines for more options:
    # https://rich.readthedocs.io/en/latest/index.html
    "theme": {
        # Change timestamp color
        "logging.time": "bright_cyan",
        # Add more named styles from Rich for your own use
        "logging.level.error": "bold red",
    },
    # which theme key to use for the timestamp
    "time_style_key": "logging.time",
    "rich": {
        # you can also inject RichHandler flags here later without code changes
        "show_time": True,
        "show_path": False,
    },
    "file": {
        "when": "midnight",
        "backupCount": 10,
        "fmt": "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
    },
}


class ProcessLogBridge:
    """
    ProcessLogBridge: single-class logging bridge
    - Rich console with colored ISO+TZ timestamps
    - Severity from 'message_type' or text tokens
    - Pretty JSON (including nested JSON-in-"message")
    - Traceback text reflow + syntax-highlight (via Rich)
    - Tee raw lines to per-process log files
    - Multi-line JSON reassembly (brace-balanced)
    """

    # ---------- constants ----------
    _LEVEL_WORD = re.compile(r"\b(DEBUG|INFO|WARNING|ERROR|CRITICAL|FATAL)\b", re.IGNORECASE)
    _MESSAGE_TYPE_TO_LEVEL: Dict[str, int] = {
        "trace": logging.DEBUG,
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "other": logging.INFO,
        "success": logging.INFO,
        "warning": logging.WARNING,
        "warn": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
        "fatal": logging.CRITICAL,
    }

    _TB_START = "Traceback (most recent call last):"
    _TB_CHAIN_1 = "During handling of the above exception, another exception occurred:"
    _TB_CHAIN_2 = "The above exception was the direct cause of the following exception:"
    _REQUEST_REPORTING_INNER = re.compile(r'Request reporting:\s*\{(?P<inner>.*?)\}\s*",', re.IGNORECASE | re.DOTALL)
    _META_FIELDS = ["user_id", "Timestamp", "source", "message_type", "request_id"]
    _META_REGEXES = {f: re.compile(rf'"{f}"\s*:\s*"(?P<val>[^"]*)"', re.IGNORECASE) for f in _META_FIELDS}

    # ---------- construction ----------
    def __init__(
        self, level: str = "INFO", runner_log_file: Optional[str] = None, config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the logging bridge.

        :params:
            level (str):
                The minimum log severity for console output.
                Defaults to `"INFO"`.
            runner_log_file (str | None):
                Optional path to a file where all logs
                (from all attached processes) will be written.
                If provided, a `TimedRotatingFileHandler` is configured.
            config (dict | None):
                Optional override configuration that merges with
                the built-in `log_cfg`. Supports overriding theme,
                rich handler settings, and file handler settings.

        Notes:
            - Creates a Rich console.
            - Reconfigures the root logger with rich + optional file handlers.
            - Initializes per-stream state storage for subprocess drains.
        """
        self.level_name = level.upper()
        self.runner_log_file = runner_log_file
        cfg = copy.deepcopy(log_cfg)
        if config:
            cfg.update(config)

        # ---- THEME (colors/styles) ----
        # Rich theme docs support names ("cyan", "bright_cyan", "magenta"),
        # hex ("#34d399"), rgb("rgb(52,211,153)"), or color(index) ("color(118)").
        # We'll merge user theme over a sensible default.
        theme_styles = {"logging.time": "bright_cyan"}
        theme_styles.update(cfg.get("theme", {}))

        self._time_style_key = cfg.get("time_style_key", "logging.time")

        # rich console / handler
        theme = Theme(theme_styles)
        self.console: Console = Console(theme=theme)

        # Base kwargs with safe defaults, then let config["rich"] override.
        rh_kwargs = {
            "console": self.console,
            "rich_tracebacks": False,
            "markup": False,
            "show_time": True,
            "show_path": False,
            "omit_repeated_times": False,
            # we provide a callable that returns colored Text each time
            "log_time_format": self._rich_time_text,
        }
        rh_kwargs.update(cfg.get("rich", {}))

        self.rich_handler: RichHandler = RichHandler(**rh_kwargs)
        self.rich_handler.setLevel(getattr(logging, self.level_name, logging.INFO))
        self.rich_handler.setFormatter(logging.Formatter("%(message)s"))

        # file handler (optional)
        self.file_handler: Optional[TimedRotatingFileHandler] = None
        if runner_log_file:
            file_cfg = cfg.get("file", {})
            when = file_cfg.get("when", "midnight")
            backup_count = int(file_cfg.get("backupCount", 7))
            encoding = file_cfg.get("encoding", "utf-8")
            fmt = file_cfg.get("fmt", "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s")
            Path(runner_log_file).parent.mkdir(parents=True, exist_ok=True)
            self.file_handler = TimedRotatingFileHandler(
                runner_log_file, when=when, backupCount=backup_count, encoding=encoding
            )
            self.file_handler.setLevel(logging.DEBUG)
            # keep tz-aware timestamps for file logs
            self.file_handler.setFormatter(self._TZFormatter(fmt=fmt))

        # root logger config
        root = logging.getLogger()
        root.setLevel(logging.DEBUG)
        root.handlers.clear()
        root.addHandler(self.rich_handler)
        if self.file_handler:
            root.addHandler(self.file_handler)

        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.info("Runner logging initialized (rich console enabled)")

        # Per-stream state: (process_name, stream_tag) -> state
        # state keys: tee(TextIO), buffer(list[str]), balance(int), collecting(bool), logger(logging.Logger)
        self._streams: Dict[Tuple[str, str], Dict[str, Any]] = {}

    # ---------- public API ----------
    def attach_process_logger(self, process, process_name: str, log_file: str) -> None:
        """
        Drain stdout/stderr in background threads, pretty-print to terminal, mirror raw to file.
        Spawns background threads that:
        - Continuously read from `process.stdout` and `process.stderr`.
        - Pretty-print parsed output to the console.
        - Mirror raw lines to the specified log file.
        :param process: A running subprocess object with `.stdout` and `.stderr`
            file-like streams opened in text mode.
        :param process_name (str): Logical label for this process. Used as logger name prefix.
        :param log_file (str): File to write raw mirror logs to. Created if missing.
        Notes:
            - Two threads are spawned: one for stdout, one for stderr.
            - Per-stream state (buffer, JSON reassembly, tee handle) is created.
        """
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        tee_out = open(log_file, "a", encoding="utf-8")
        tee_err = open(log_file, "a", encoding="utf-8")
        self._streams[(process_name, "STDOUT")] = self._make_stream_state(process_name, tee_out)
        self._streams[(process_name, "STDERR")] = self._make_stream_state(process_name, tee_err)

        t_out = threading.Thread(target=self._drain_pipe, args=(process.stdout, process_name, "STDOUT"), daemon=True)
        t_err = threading.Thread(target=self._drain_pipe, args=(process.stderr, process_name, "STDERR"), daemon=True)
        t_out.start()
        t_err.start()

    # ---------- helpers: logging/time ----------
    @classmethod
    def _now_local(cls) -> datetime:
        """
        :return: datetime: The current timezone-aware local datetime.
        """
        return datetime.now().astimezone()

    def _rich_time_text(self, record=None, date=None):
        """
        :param record: Unused, but required for compatibility with RichHandler's
                `log_time_format` signature.
        :param date: Unused. Rich passes this parameter but it is not needed.
        :return: Text: A Rich `Text` object containing a formatted timestamp using
                the configured `self._time_style_key`.
        """
        now = self._now_local()
        return Text(f"[{now.strftime('%Y-%m-%d %H:%M:%S')} {now.tzname()}]", style=self._time_style_key)

    class _TZFormatter(logging.Formatter):
        """
        File-handler formatter that emits timezone-aware timestamps.
        :extend: logging.Formatter
        """
        def formatTime(self, record, datefmt=None):
            """
            :param: record: A log record.
            :param datefmt (str | None): Ignored. Exists for Formatter API compatibility.
            :return: str: Timestamp formatted as `"YYYY-MM-DD HH:MM:SS <TZNAME>"`.
            """
            dt = datetime.fromtimestamp(record.created).astimezone()
            return f"{dt.strftime('%Y-%m-%d %H:%M:%S')} {dt.tzname()}"

    # ---------- helpers: per-stream state ----------
    def _make_stream_state(self, process_name: str, tee: TextIO) -> Dict[str, Any]:
        """
        Create an initial per-stream state dictionary.
        :param process_name (str): Logical name for the process whose output is being handled.
        :param tee (TextIO): Writable file-like object used to mirror raw log lines.
        :return: dict: A dict containing:
                    - "tee": file handle for mirroring.
                    - "buffer": list used for multiline JSON reassembly.
                    - "balance": brace balance counter.
                    - "collecting": whether multi-line JSON parsing is active.
                    - "logger": Python logger for this process's output.
        """
        return {
            "tee": tee,
            "buffer": [],
            "balance": 0,
            "collecting": False,
            "logger": logging.getLogger(process_name),
        }

    @staticmethod
    def _write_tee(state: Dict[str, Any], raw: str) -> None:
        """
        Write a raw log line to the tee file handle.
        :param state (dict): A per-stream state dictionary.
        :param raw (str): The raw line to mirror.
        Notes: Exceptions are silently ignored so logging never causes crashes.
        """
        try:
            state["tee"].write(f"{raw}\n")
        except Exception:
            pass

    @staticmethod
    def _close_stream(state: Dict[str, Any]) -> None:
        """
        Flush and close the tee file handle for a stream.
        :param state (dict): A per-stream state dictionary.
        Notes: Errors during closure are ignored.
        """
        try:
            state["tee"].flush()
            state["tee"].close()
        except Exception:
            pass

    # ---------- pipe draining ----------
    def _drain_pipe(self, pipe, process_name: str, stream_tag: str) -> None:
        """
        Continuously read from a subprocess pipe and process each line.
        This method:
        - Retrieves the per-stream state.
        - Reads lines until EOF.
        - Passes each line to `_handle_line()`.
        - Cleans up the pipe and tee file when finished.
        :param pipe: A file-like object (stdout or stderr from a subprocess).
        :param process_name (str): Label for the process.
        :param stream_tag (str): `"STDOUT"` or `"STDERR"`—used as part of the state key.
        """
        key = (process_name, stream_tag)
        state = self._streams[key]
        try:
            for line in iter(pipe.readline, ""):
                self._handle_line(state, line.rstrip("\n"))
        finally:
            try:
                pipe.close()
            except Exception:
                pass
            self._close_stream(state)

    # ---------- line handling ----------
    def _handle_line(self, state: Dict[str, Any], line: str) -> None:
        """
        Handle a single log line from a process.
        Steps:
            1. Mirror raw line to tee file.
            2. Attempt strict or fragmentary JSON parsing.
            3. Otherwise apply multiline JSON reassembly logic.
            4. If none apply, log as plain text.
        :param state (dict): The per-stream state dict.
        :param line (str): The raw line to process.
        """
        if line == "":
            self._write_tee(state, line)
            return

        # Mirror raw first
        self._write_tee(state, line)

        # Single-line JSON?
        obj = self._try_parse_json_fragment(line)
        if obj is not None:
            self._emit_json_block(state, obj)
            return

        # Multi-line accumulation
        if not state["collecting"]:
            if self._reasm_start_if_jsonish(state, line):
                if state["balance"] <= 0:  # closed on same line
                    block = self._reasm_flush(state)
                    self._emit_collected(state, block)
                return
            # Plain text fallback
            self._emit_text_line(state, line)
            return

        # we are collecting
        self._reasm_add(state, line)
        if self._reasm_should_flush(state, line):
            block = self._reasm_flush(state)
            self._emit_collected(state, block)

    # ---------- reassembler (stateful, no extra classes) ----------
    @staticmethod
    def _count_braces_outside_quotes(s: str) -> int:
        """
        Count net brace balance `{` minus `}` ignoring quoted strings.
        :param s (str): A text line.
        :return int: Net count (`+1` for `{`, `-1` for `}`), ignoring content inside double quotes.
        """
        depth = 0
        in_str = False
        esc = False
        for ch in s:
            if esc:
                esc = False
                continue
            if ch == "\\":
                esc = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
        return depth

    def _reasm_start_if_jsonish(self, state: Dict[str, Any], line: str) -> bool:
        """
        Begin multiline JSON collection if line contains an opening brace.
        :param state (dict): The per-stream state.
        :param line (str): The raw line.
        :return bool: True if collection has begun, False otherwise.
        """
        if "{" in line:
            state["buffer"] = [line]
            state["balance"] = self._count_braces_outside_quotes(line)
            state["collecting"] = True
            return True
        return False

    def _reasm_add(self, state: Dict[str, Any], line: str) -> None:
        """
        Append a line to the JSON reassembly buffer.
        :param state (dict): Per-stream state dictionary.
        :param line (str): The next line in the JSON block.
        """
        state["buffer"].append(line)
        state["balance"] += self._count_braces_outside_quotes(line)

    @staticmethod
    def _reasm_should_flush(state: Dict[str, Any], line: str) -> bool:
        """
        Determine whether collected JSON should be flushed.
        Flush when:
            - Brace balance <= 0, or
            - The line ends a request block containing `"request_id"`.
        :param state (dict): Per-stream state.
        :param line (str): The line just added.
        :return bool: True if buffer should be flushed.
        """
        if state["balance"] <= 0:
            return True
        if '"request_id"' in line and line.rstrip().endswith("}"):
            return True
        return False

    @staticmethod
    def _reasm_flush(state: Dict[str, Any]) -> str:
        """
        Flush collected JSON text and reset reassembly state.
        :param state (dict): The per-stream reassembly state.
        :return str: The combined block as a single string.
        """
        text = "\n".join(state["buffer"]).strip()
        state["buffer"].clear()
        state["balance"] = 0
        state["collecting"] = False
        return text

    # ---------- severity ----------
    def _infer_level_from_message_type(self, record: Dict[str, Any]) -> int:
        """
        Infer logging level from a JSON record's `message_type` field.
        :param record (dict): Parsed JSON record containing `"message_type"`.
        :return int: A logging level constant (e.g., logging.INFO, logging.ERROR).
        """
        mt = str(record.get("message_type", "")).strip().lower()
        return self._MESSAGE_TYPE_TO_LEVEL.get(mt, logging.INFO)

    def _infer_level_from_text(self, line: str, default: int = logging.INFO) -> int:
        """
        Infer a log level from textual content.
        Rules:
            - If the line contains a severity word (INFO, WARNING, ERROR, etc.)
              that level is returned.
            - If the line looks like a traceback, ERROR is returned.
            - Otherwise, the provided default is used.
        :param line (str): The raw text line.
        :param default (int): Fallback level.
        :return int: Logging level constant.
        """
        if not line:
            return default
        m = self._LEVEL_WORD.search(line)
        if not m:
            if "traceback" in line.lower():
                return logging.ERROR
            return default
        word = m.group(1).upper()
        return logging.CRITICAL if word == "FATAL" else getattr(logging, word, default)

    # ---------- json helpers ----------
    @staticmethod
    def _pretty_json(obj: Any) -> str:
        """
        Pretty-print a JSON object.
        :param obj (Any): Any JSON-serializable object.
        :return str: Indented JSON, or `str(obj)` on failure.
        """
        try:
            return json.dumps(obj, indent=2, ensure_ascii=False)
        except Exception:
            return str(obj)

    @staticmethod
    def _try_parse_json_fragment(text: str) -> Optional[Dict[str, Any]]:
        """
        Try to parse a JSON dictionary from a text line.
        Attempts:
            1. Full strict `json.loads(text)`
            2. Extract fragment between first `{` and last `}` and parse that.
        :param text (str): Input line.
        :return dict | None: Parsed JSON as a dictionary, or None if not parseable.
        """
        if not text:
            return None
        # strict
        try:
            obj = json.loads(text)
            return obj if isinstance(obj, dict) else {"message": obj}
        except Exception:
            pass
        # first {...}
        s = text.find("{")
        e = text.rfind("}")
        if s != -1 and e != -1 and e > s:
            frag = text[s: e + 1]
            try:
                obj = json.loads(frag)
                return obj if isinstance(obj, dict) else {"message": obj}
            except Exception:
                return None
        return None

    @staticmethod
    def _lenient_inner_json_parse(val: Any) -> Optional[Any]:
        """
        Attempt lenient JSON parsing of a string containing nested JSON.
        Strategy:
            - If value is not a string, return None.
            - If it doesn't begin with `{` or `[`, return None.
            - Try strict `json.loads()`.
            - Otherwise, clean escape sequences and attempt again.
        :param val (Any): Possibly nested JSON-like string.
        :return Any | None: Parsed JSON object, or None if not parseable.
        """
        if not isinstance(val, str):
            return None
        s = val.strip()
        if not s:
            return None
        if not (s.lstrip().startswith("{") or s.lstrip().startswith("[")):
            return None
        # strict
        try:
            return json.loads(s)
        except Exception:
            pass
        # mild cleanup: unescape \n \t \r and drop trailing commas
        s2 = s.replace("\\r", "\r").replace("\\t", "\t").replace("\\n", "\n")
        s2 = re.sub(r",\s*(?=[}\]])", "", s2)
        s2 = re.sub(r"\n{3,}", "\n\n", s2)
        try:
            return json.loads(s2)
        except Exception:
            return None

    # ---------- special NeuroSan block ----------
    def _rebuild_neurosan_request_reporting(self, text_block: str) -> Optional[Dict[str, Any]]:
        """
        Detect and rebuild NeuroSan request-reporting blocks.
        These blocks appear in raw logs as text containing:
            `Request reporting: { ...nested_json... }"`
        This method extracts:
            - The inner JSON payload.
            - Additional metadata fields such as user_id, source, Timestamp, etc.
        :param text_block (str): Full text block potentially containing request-reporting info.
        :return dict | None: A reconstructed JSON dictionary if matched, or None otherwise.
        """
        m = self._REQUEST_REPORTING_INNER.search(text_block)
        if not m:
            return None
        inner_src = "{" + m.group("inner").strip() + "}"
        try:
            inner = json.loads(inner_src)
        except Exception:
            inner = inner_src
        out: Dict[str, Any] = {"message": inner}
        for f, rx in self._META_REGEXES.items():
            mm = rx.search(text_block)
            if mm:
                out[f] = mm.group("val")
        out.setdefault("Timestamp", self._now_local().isoformat())
        out.setdefault("source", "HttpServer")
        out.setdefault("message_type", "Other")
        return out

    # ---------- traceback helpers ----------
    def _normalize_traceback_str(self, message: str) -> str:
        """
        Normalize traceback strings for consistent pretty-printing.
        Steps:
            - Unescape newline/tab sequences.
            - Insert strategic newlines around typical traceback markers.
            - Collapse excessive blank lines.
        :param message (str): Raw traceback-like text.
        :return str: Cleaned, readable traceback text.
        """
        message = message or ""
        message = message.replace("\\r", "\r").replace("\\t", "\t").replace("\\n", "\n").replace('\\"', '"')
        for old, new in [
            (self._TB_START, f"\n{self._TB_START}\n"),
            (self._TB_CHAIN_1, f"\n{self._TB_CHAIN_1}\n"),
            (self._TB_CHAIN_2, f"\n{self._TB_CHAIN_2}\n"),
            ("  File", "\n  File"),
            ('File "', '\nFile "'),
            ("ValueError:", "\nValueError:"),
            ("TypeError:", "\nTypeError:"),
            ("RuntimeError:", "\nRuntimeError:"),
            ("ImportError:", "\nImportError:"),
            ("Exception:", "\nException:"),
            ("Error:", "\nError:"),
        ]:
            message = message.replace(old, new)
        message = re.sub(r"\n{3,}", "\n\n", message)
        return message.strip()

    def _looks_like_traceback(self, s: str) -> bool:
        """
        Detect whether a string resembles a Python traceback.
        :param s (str): Input text.
        :return bool: True if the text appears to contain traceback markers.
        """
        if self._TB_START in (s or ""):
            return True
        return bool(re.search(r'File ".*?", line \d+(?:, in .*)?', s or ""))

    # ---------- emitters ----------
    def _src_header(self, process_name: str, source: Optional[str]) -> str:
        """
        Build a source header combining process name and optional source tag.
        :param process_name (str): Name of the originating process.
        :param source (str | None): Optional metadata source.
        :return str: `"proc_name:source"` or `"proc_name"` if no source.
        """
        return f"{process_name}:{source}" if source else process_name

    def _emit_json_block(self, state: Dict[str, Any], record: Dict[str, Any]) -> None:
        """
        Emit a fully parsed JSON record to the logger.
        Steps:
            1. Infer log level from `message_type`.
            2. Build header including process name and optional source.
            3. Parse nested JSON inside the `"message"` field (if present).
            4. Pretty-print JSON.
            5. If the message looks like traceback text, print a Rich-formatted traceback.
        :param state (dict): Per-stream logging state.
        :param record (dict): Parsed JSON dictionary representing the log event.
        """
        level = self._infer_level_from_message_type(record)
        src = str(record.get("source") or "").strip() or None
        header = self._src_header(state["logger"].name, src)

        # Display copy
        display_rec = dict(record)
        inner = self._lenient_inner_json_parse(display_rec.get("message"))
        if inner is not None:
            display_rec["message"] = inner

        body = self._pretty_json(display_rec)
        self._log(state, level, header + "\n" + body)

        # If message was traceback-like text, pretty print after
        msg = record.get("message")
        if isinstance(msg, str):
            tb_text = self._normalize_traceback_str(msg)
            if self._looks_like_traceback(tb_text):
                self._log(state, level, header + " (traceback)")
                self.console.print(Syntax(tb_text, "pytb", word_wrap=False))

    def _emit_text_line(self, state: Dict[str, Any], line: str) -> None:
        """
        Emit a plain text line to the logger.
        :param state (dict): Per-stream logging state.
        :param line (str): Raw log line.
        Notes: Severity is inferred automatically via `_infer_level_from_text()`.
        """
        level = self._infer_level_from_text(line, logging.INFO)
        header = self._src_header(state["logger"].name, None)
        self._log(state, level, header + " - " + line)

    def _emit_collected(self, state: Dict[str, Any], block: str) -> None:
        """
        Emit a reconstructed multiline block.
        Decision logic:
            - If block parses as JSON → emit as JSON.
            - If it matches NeuroSan request-reporting → rebuild + emit.
            - Otherwise → treat as text (flatten whitespace).
        :param state (dict): Per-stream state.
        :param block (str): Reassembled multiline block.
        """
        obj = self._try_parse_json_fragment(block)
        if obj is not None:
            self._emit_json_block(state, obj)
            return

        rebuilt = self._rebuild_neurosan_request_reporting(block)
        if rebuilt is not None:
            self._emit_json_block(state, rebuilt)
            return

        flat = " ".join(p.strip() for p in block.splitlines() if p.strip())
        self._emit_text_line(state, flat)

    # ---------- logging wrapper ----------
    @staticmethod
    def _log(state: Dict[str, Any], level: int, msg: str) -> None:
        """
        Log a message using the appropriate logger method.
        :param state (dict): Per-stream state containing a logger.
        :param level (int): Logging level constant.
        :param msg (str): Message to emit.
        Notes: Calls the appropriate severity method (debug/info/warning/error/...).
        """
        lg = state["logger"]
        if level >= logging.CRITICAL:
            lg.critical(msg)
        elif level >= logging.ERROR:
            lg.error(msg)
        elif level >= logging.WARNING:
            lg.warning(msg)
        elif level >= logging.INFO:
            lg.info(msg)
        else:
            lg.debug(msg)
