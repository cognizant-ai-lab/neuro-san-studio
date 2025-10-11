#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import csv
import json
import time
import random
import subprocess
import json as _json
from typing import Dict, Any, Tuple, Optional, List, Callable, Iterable

# Neuro-SAN client
from neuro_san.client.agent_session_factory import AgentSessionFactory
from neuro_san.client.streaming_input_processor import StreamingInputProcessor

PORT = 30012


class AgentBenchmarkRunner:
    """
    Generic agent benchmarking utility.

    Features:
      - Pluggable dataset loader (default: GSM8K via HF or local JSONL)
      - Fresh conversation thread per example to prevent leakage
      - CoT / final-answer-only prompting
      - Robust numeric extraction (GSM8K '#### <number>' + fallback)
      - CSV/JSONL outputs + basic latency & accuracy metrics
      - Minimal dependencies on your agent stack (Neuro-SAN session + StreamingInputProcessor)

    Extend/override:
      - load_data()
      - build_prompt()
      - parse_gold()
      - parse_prediction()
      - evaluate_item()
    """

    FINAL_ANSWER_TOKEN = "####"
    NUM_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")

    def __init__(
            self,
            agent_name: str = "thinking_module",
            connection: str = "direct",
            host: str = "localhost",
            port: int = PORT,
            local_externals_direct: bool = False,
            agent_manifest_file: str = "registries/manifest.hocon",
            agent_tool_path: str = "coded_tools",
            default_timeout_ms: float = 120_000.0,
            chat_filter: Optional[Dict[str, Any]] = None,
            dataset_loader: Optional[Callable[..., List[Dict[str, Any]]]] = None,
            # add these two:
            python_prog: Optional[str] = None,
            python_prog_args: Optional[List[str]] = None,
    ):
        self.agent_name = agent_name
        self.connection = connection
        self.host = host
        self.port = port
        self.local_externals_direct = local_externals_direct
        self.default_timeout_ms = default_timeout_ms
        self.chat_filter = chat_filter or {"chat_filter_type": "MAXIMAL"}
        self.python_prog = python_prog
        self.python_prog_args = python_prog_args or []

        # Environment for Neuro-SAN
        os.environ["AGENT_MANIFEST_FILE"] = agent_manifest_file
        os.environ["AGENT_TOOL_PATH"] = agent_tool_path

        # Optional injected dataset loader
        self._dataset_loader = dataset_loader

        # Will be created on start()
        self._session = None

    # ------------------ Lifecycle ------------------

    def start(self, user_meta: Optional[Dict[str, Any]] = None):
        if self.python_prog:
            # No agent session needed in python program mode.
            self._session = None
            return
        factory = AgentSessionFactory()
        metadata = {"user_id": os.environ.get("USER")}
        if user_meta:
            metadata.update(user_meta)
        self._session = factory.create_session(
            self.connection,
            self.agent_name,
            self.host,
            self.port,
            self.local_externals_direct,
            metadata,
        )

    def close(self):
        if self._session is not None:
            self._session.close()
            self._session = None

    # ------------------ Threads & Turns ------------------

    def new_thread(self, prompt_seed: str = "", timeout_ms: Optional[float] = None) -> Dict[str, Any]:
        return {
            "last_chat_response": None,
            "prompt": prompt_seed,
            "timeout": self.default_timeout_ms if timeout_ms is None else timeout_ms,
            "num_input": 0,
            "user_input": None,
            "sly_data": None,
            "chat_filter": self.chat_filter,
        }

    def single_turn(self, thread: Dict[str, Any], text: str) -> Tuple[Optional[str], Dict[str, Any]]:
        thread["user_input"] = text
        if self.python_prog:
            # Program mode
            resp = self._run_python_program(text, timeout_ms=thread.get("timeout", self.default_timeout_ms))
            thread["last_chat_response"] = resp
            return resp, thread

        # Agent mode (existing behavior)
        if self._session is None:
            raise RuntimeError("Session is not started. Call start() first.")
        inp = StreamingInputProcessor(
            "DEFAULT",
            "/tmp/benchmark_agent_thinking.txt",
            self._session,
            None,
        )
        thread = inp.process_once(thread)
        return thread.get("last_chat_response"), thread

    # ------------------ Dataset Loading ------------------

    def load_data(
        self,
        *,
        task: str = "gsm8k",
        split: str = "test",
        local_jsonl: Optional[str] = None,
        seed: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Returns a list of dicts with keys: id, question, answer (gold text).

        Override or inject via dataset_loader for other tasks.
        """
        if self._dataset_loader:
            return self._dataset_loader(task=task, split=split, local_jsonl=local_jsonl, seed=seed)

        # If a local file is provided, we don't care about task name.
        if local_jsonl:
            data = []
            with open(local_jsonl, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    rec = json.loads(line)
                    q = rec.get("question") or rec.get("prompt") or ""
                    a = rec.get("answer") or rec.get("gold") or ""
                    data.append({"id": rec.get("id", f"local-{i}"), "question": q, "answer": a})
            return data

        # Otherwise fall back to known datasets
        if task.lower() != "gsm8k":
            raise ValueError(f"Unknown task '{task}'. Provide --local-jsonl or a dataset_loader.")

        if local_jsonl:
            data = []
            with open(local_jsonl, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    rec = json.loads(line)
                    q = rec.get("question") or rec.get("prompt") or ""
                    a = rec.get("answer") or rec.get("gold") or ""
                    data.append({"id": rec.get("id", f"local-{i}"), "question": q, "answer": a})
            return data

        try:
            from datasets import load_dataset  # type: ignore
        except Exception as e:
            raise RuntimeError(
                "HuggingFace `datasets` not available. Install it (`pip install datasets`) "
                "or pass local_jsonl."
            ) from e

        ds = load_dataset("gsm8k", "main")
        if split not in ds:
            raise ValueError(f"Split '{split}' not found. Available: {list(ds.keys())}")

        out = []
        for i, row in enumerate(ds[split]):
            out.append({"id": row.get("id", f"{split}-{i}"),
                        "question": row["question"],
                        "answer": row["answer"]})
        random.Random(seed).shuffle(out)
        return out

    # ------------------ Prompting ------------------

    def build_prompt(
            self,
            question: str,
            *,
            fewshot_prefix: Optional[str],
            show_work: bool,
            final_token: str = None,
            answer_format: str = "number",
    ) -> str:
        final_token = final_token or self.FINAL_ANSWER_TOKEN

        if answer_format == "list-json":
            instruction = (
                "You are sorting a list of integers. Reason briefly, then follow the output format EXACTLY."
                if show_work else
                "Sort the list of integers correctly. Do NOT include your reasoning. Follow the output format EXACTLY."
            )
            format_rule = (
                f"OUTPUT FORMAT (must match exactly):\n"
                f"  {final_token} [a,b,c]\n"
                f"- No spaces anywhere inside the brackets.\n"
                f"- Only integers, comma-separated.\n"
                f"- No extra text before or after the line.\n"
                f"- Preserve duplicates. Use ascending order.\n"
                f"Example:\n"
                f"  Input: [3, 1, 2, 2]\n"
                f"  Output:\n"
                f"  {final_token} [1,2,2,3]"
            )
        else:
            instruction = (
                "You are solving a numeric problem."
                if show_work else
                "Solve the problem correctly. You may use scratch work internally, but DO NOT include your full reasoning."
            )
            format_rule = f"At the end, output the final numeric answer on its own line as '{final_token} <number>'."

        parts = []
        if fewshot_prefix:
            parts.append(fewshot_prefix.strip())
        parts += [
            "### Task",
            instruction,
            format_rule,
            "",
            "### Problem",
            question.strip(),
            "",
            "### Answer",
        ]
        return "\n".join(parts)

    # ------------------ Parsing ------------------

    def parse_prediction_list_json(self, text: str, *, final_token: str) -> Optional[list]:
        if not text:
            return None
        pos = text.rfind(final_token)
        segment = text[pos + len(final_token):] if pos != -1 else text
        # find first '[' ... ']' in the tail
        try:
            start = segment.index("[")
            end = segment.rindex("]") + 1
            js = segment[start:end]
            parsed = _json.loads(js)
            if isinstance(parsed, list):
                # coerce to ints if they look like ints
                out = []
                for v in parsed:
                    if isinstance(v, (int, float)):
                        out.append(int(v))
                    elif isinstance(v, str) and v.strip().lstrip("-").isdigit():
                        out.append(int(v))
                    else:
                        return None
                return out
        except Exception:
            return None
        return None

    def _run_python_program(self, text: str, timeout_ms: float) -> str:
        """
        Calls the configured python program, passing `text` on stdin.
        Expects the program to print the full response to stdout.
        """
        cmd = ["python3", self.python_prog] + list(self.python_prog_args)
        proc = subprocess.run(
            cmd,
            input=text.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=max(0.001, timeout_ms / 1000.0),
        )
        # Prefer stdout; if empty but there is stderr, surface it.
        out = proc.stdout.decode("utf-8", errors="ignore").strip()
        if not out and proc.stderr:
            out = proc.stderr.decode("utf-8", errors="ignore").strip()
        return out

    def _normalize_number(self, s: str) -> str:
        s = s.replace(",", "").strip()
        try:
            v = float(s)
            return str(int(v)) if v.is_integer() else str(v)
        except Exception:
            return s

    def parse_gold(self, gold_text: str, *, final_token: str = None, answer_format: str = "number"):
        if answer_format == "list-json":
            # gold_text is a canonical JSON list string
            try:
                arr = _json.loads(gold_text)
                return [int(x) for x in arr]
            except Exception:
                return None
        return self.parse_prediction(gold_text, final_token=final_token)

    def parse_prediction(self, text: str, *, final_token: str = None, answer_format: str = "number"):
        token = final_token or self.FINAL_ANSWER_TOKEN
        if answer_format == "list-json":
            return self.parse_prediction_list_json(text, final_token=token)
        # numeric (existing behavior)
        if not text:
            return None
        pos = text.rfind(token)
        if pos != -1:
            tail = text[pos + len(token):]
            m = self.NUM_RE.search(tail)
            if m:
                return self._normalize_number(m.group(0))
        all_nums = list(self.NUM_RE.finditer(text))
        if all_nums:
            return self._normalize_number(all_nums[-1].group(0))
        return None

    # ------------------ Single Item Eval ------------------

    def evaluate_item(
            self,
            question: str,
            gold: str,
            *,
            per_item_timeout_ms: Optional[float] = None,
            retries: int = 0,
            final_token: str = "####",
            answer_format: str = "number",
    ) -> Dict[str, Any]:
        gold_parsed = self.parse_gold(gold, final_token=final_token, answer_format=answer_format)
        prompt = question.strip()
        start = time.time()
        response, err = None, None
        for attempt in range(retries + 1):
            try:
                thread = self.new_thread(timeout_ms=per_item_timeout_ms)
                response, _ = self.single_turn(thread, prompt)
                break
            except Exception as e:
                err = str(e)
                if attempt < retries:
                    time.sleep(0.5)

        latency = time.time() - start
        pred_parsed = self.parse_prediction(response or "", final_token=final_token, answer_format=answer_format)

        if answer_format == "list-json":
            is_correct = (
                        isinstance(pred_parsed, list) and isinstance(gold_parsed, list) and pred_parsed == gold_parsed)
        else:
            is_correct = (pred_parsed is not None and gold_parsed is not None and pred_parsed == gold_parsed)

        return {
            "question": question,
            "gold": gold,
            "gold_extracted": gold_parsed,
            "response": response if response is not None else f"[ERROR] {err}",
            "pred_extracted": pred_parsed,
            "correct": bool(is_correct),
            "latency_sec": round(latency, 3),
            "status": "ok" if response is not None else "error",
            "error": (err if response is None else None),
        }

    # ------------------ Benchmark Loop ------------------

    def evaluate(
            self,
            data: Iterable[Dict[str, Any]],
            *,
            limit: Optional[int] = None,
            per_item_timeout_ms: Optional[float] = None,
            retries: int = 0,
            progress_every: int = 10,
            sample_retries: int = 2,  # NEW: per-sample reruns
            retry_backoff_ms: int = 500,  # NEW: base backoff
            exclude_errors: bool = False,  # NEW: control denominator
            answer_format: str = "number", final_token: str = "####") -> Dict[str, Any]:
        items = list(data) if not isinstance(data, list) else data
        if limit is not None:
            items = items[:limit]

        results = []
        correct = 0
        latencies = []
        processed = 0  # items counted in denominator (may exclude persistent errors)

        for i, ex in enumerate(items, 1):
            attempt = 0
            backoff = retry_backoff_ms / 1000.0
            final_r = None

            while attempt <= sample_retries:
                r = self.evaluate_item(
                    ex["question"],
                    ex["answer"],
                    per_item_timeout_ms=per_item_timeout_ms,
                    retries=retries,
                    final_token=final_token,
                    answer_format=answer_format,
                )
                final_r = {"id": ex.get("id", str(i)), **r}

                if r["status"] == "ok":
                    break  # success
                attempt += 1
                if attempt <= sample_retries:
                    # optional: refresh session every other rerun (helps flaky transports)
                    try:
                        self.close()
                        self.start(user_meta={"benchmark": "rerun"})
                    except Exception:
                        pass
                    time.sleep(backoff)
                    backoff *= 2  # exponential

            # accounting
            results.append(final_r)
            if final_r["status"] == "ok":
                processed += 1
                correct += int(final_r["correct"])
                latencies.append(final_r["latency_sec"])
            else:
                if not exclude_errors:
                    processed += 1
                    latencies.append(final_r["latency_sec"])

            if progress_every and (i % progress_every == 0 or i == len(items)):
                denom = processed if processed > 0 else 1
                print(f"[{i}/{len(items)}] acc_so_far={correct / denom:.3f} last_latency={final_r['latency_sec']:.2f}s "
                      f"(attempts={attempt})")

        denom = processed if processed > 0 else 1
        accuracy = correct / denom
        avg_latency = (sum(latencies) / len(latencies)) if latencies else 0.0
        p95_latency = self._percentile(latencies, 95) if latencies else 0.0

        return {
            "accuracy": accuracy,
            "count": denom,
            "avg_latency_sec": avg_latency,
            "p95_latency_sec": p95_latency,
            "results": results,
        }

    # ------------------ Output ------------------

    def save_results(self, payload: Dict[str, Any], tag: str = "gsm8k") -> Tuple[str, str]:
        ts = time.strftime("%Y%m%d_%H%M%S")
        base_csv = f"results_{tag}_{ts}.csv"
        base_jsonl = f"results_{tag}_{ts}.jsonl"

        with open(base_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=[
                "id", "question", "gold", "gold_extracted", "response",
                "pred_extracted", "correct", "latency_sec"
            ])
            w.writeheader()
            for r in payload["results"]:
                w.writerow({
                    "id": r["id"],
                    "question": r["question"],
                    "gold": r["gold"],
                    "gold_extracted": r["gold_extracted"],
                    "response": r["response"],
                    "pred_extracted": r["pred_extracted"],
                    "correct": r["correct"],
                    "latency_sec": r["latency_sec"],
                })

        with open(base_jsonl, "w", encoding="utf-8") as f:
            meta = {k: v for k, v in payload.items() if k != "results"}
            f.write(json.dumps({"_meta": meta}, ensure_ascii=False) + "\n")
            for r in payload["results"]:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

        return base_csv, base_jsonl

    # ------------------ Utils ------------------

    @staticmethod
    def _percentile(arr: List[float], p: float) -> float:
        if not arr:
            return 0.0
        arr = sorted(arr)
        k = (len(arr) - 1) * (p / 100.0)
        f = int(k)
        c = min(f + 1, len(arr) - 1)
        if f == c:
            return arr[f]
        return arr[f] + (k - f) * (arr[c] - arr[f])


# ------------------ Example CLI usage ------------------

if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Generic Agent Benchmark Runner (GSM8K by default).")
    ap.add_argument("--task", default="gsm8k", help="Task name (default: gsm8k)")
    ap.add_argument("--split", default="test", choices=["train", "test"], help="Dataset split")
    ap.add_argument("--local-jsonl", help="Path to local JSONL with fields: question, answer, [id]")
    ap.add_argument("--limit", type=int, help="Limit number of problems")
    ap.add_argument("--seed", type=int, default=0, help="Shuffle seed for selection")
    ap.add_argument("--timeout-ms", type=float, default=120_000.0, help="Per-item timeout (ms)")
    ap.add_argument("--retries", type=int, default=0, help="Retries on transport errors/timeouts")

    ap.add_argument("--agent-name", default="thinking_module", help="Agent network name")
    ap.add_argument("--connection", default="direct", help="Connection type")
    ap.add_argument("--host", default="localhost", help="Agent host")
    ap.add_argument("--port", type=int, default=30011, help="Agent port")

    ap.add_argument("--sample-retries", type=int, default=2,
                    help="Max per-item reruns when the platform throws (default: 2)")
    ap.add_argument("--retry-backoff-ms", type=int, default=500,
                    help="Base backoff in ms between retries; doubles each attempt (default: 500)")
    ap.add_argument("--exclude-errors", action="store_true",
                    help="Exclude items that fail after all retries from accuracy denominator")
    ap.add_argument("--answer-format", default="number",
                    choices=["number", "list-json"],
                    help="How to parse & compare final answers (default: number).")
    ap.add_argument("--final-token", default="####",
                    help="Marker token preceding the final answer (default: ####).")
    ap.add_argument("--python-prog", help="Path to a Python program to call instead of an agent")
    ap.add_argument("--python-prog-args", nargs="*", default=[], help="Args to pass to --python-prog")

    args = ap.parse_args()

    # Initialize runner
    runner = AgentBenchmarkRunner(
        agent_name=args.agent_name,
        connection=args.connection,
        host=args.host,
        port=args.port,
        default_timeout_ms=args.timeout_ms,
        # add:
        python_prog=args.python_prog,
        python_prog_args=args.python_prog_args,
     )

    # Load data
    data = runner.load_data(task=args.task, split=args.split, local_jsonl=args.local_jsonl, seed=args.seed)
    if args.limit:
        data = data[: args.limit]
    print(f"Loaded {len(data)} examples.")

    # Start session
    runner.start(user_meta={"benchmark": args.task})

    try:
        # Evaluate
        payload = runner.evaluate(
            data,
            limit=None,
            per_item_timeout_ms=args.timeout_ms,
            retries=args.retries,
            # if you already added these previously:
            sample_retries=getattr(args, "sample_retries", 2),
            retry_backoff_ms=getattr(args, "retry_backoff_ms", 500),
            exclude_errors=getattr(args, "exclude_errors", False),
            answer_format=args.answer_format,
            final_token=args.final_token,
        )
    finally:
        runner.close()

    # Report
    print("\n=== RESULTS ===")
    print(f"Count:       {payload['count']}")
    print(f"Accuracy:    {payload['accuracy']:.4f}")
    print(f"Avg latency: {payload['avg_latency_sec']:.2f}s")
    print(f"P95 latency: {payload['p95_latency_sec']:.2f}s")

    csv_path, jsonl_path = runner.save_results(payload, tag=args.task)
    print(f"\nSaved: {csv_path}\nSaved: {jsonl_path}")
