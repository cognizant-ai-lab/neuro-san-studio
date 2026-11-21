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

import argparse
import logging
import os
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any

from neuro_san.client.agent_session_factory import AgentSessionFactory
from neuro_san.client.streaming_input_processor import StreamingInputProcessor
from neuro_san.interfaces.agent_session import AgentSession
from neuro_san.message.processors.basic_message_processor import BasicMessageProcessor
from task_verification.pto_provenance.anchor_log import AnchorLog
from task_verification.pto_provenance.hr_database import HrDatabase
from task_verification.pto_provenance.provenance_graph import ProvenanceGraph

from neuro_san_studio.commands.project_environment import ProjectEnvironment


class PtoRunner:
    """
    Runs the PTO network with a real LLM, once per fault, and prints what the agent said next to what was verified.

    Each run is one chat session: fresh HR database, fresh provenance graph, one user message. The network runs in
    this process ("direct" session), so the middleware writes into the same graph this runner reads and saves.
    Output per run, in runs/<time>/: <fault>.graph.json (the whole graph). The anchors go to runs/anchors.jsonl.

    Usage, from the repo root:
        python -m task_verification.pto_provenance.pto_runner                  # every fault
        python -m task_verification.pto_provenance.pto_runner --faults none no_write
    Each run makes real LLM calls (costs money; needs the API key from .env).
    """

    AGENT_NAME: str = "pto_network"
    PROMPT: str = "I'm employee E-1042. Please schedule PTO for me on December 3, 2026."
    FAULTS: tuple[str, ...] = ("none", "no_write", "wrong_dates", "wrong_employee", "duplicate", "error")
    HERE: Path = Path(__file__).resolve().parent
    REPO_ROOT: Path = HERE.parent.parent
    MANIFEST_FILE: Path = HERE / "registries" / "manifest.hocon"

    def __init__(self) -> None:
        """Make this run's output folder, named by the current time."""
        stamp: str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.output_dir: Path = self.HERE / "runs" / stamp
        self.logger: logging.Logger = logging.getLogger(self.__class__.__name__)

    def prepare_environment(self) -> None:
        """
        Point neuro-san at this pilot's manifest, then load .env and studio's usual settings (as pilot_runner.py does).

        :raises RuntimeError: If not run from the repo root, where the network's HOCON include paths resolve from.
        """
        if Path.cwd().resolve() != self.REPO_ROOT:
            raise RuntimeError(f"Run from the repo root ({self.REPO_ROOT}); HOCON includes resolve from there.")
        # Set before apply(), which only fills unset variables, so this manifest wins over the main one.
        os.environ["AGENT_MANIFEST_FILE"] = str(self.MANIFEST_FILE)
        project_environment: ProjectEnvironment = ProjectEnvironment(str(self.REPO_ROOT))
        project_environment.load_env_file()
        project_environment.apply()

    def run(self, faults: list[str]) -> None:
        """Run one chat session per fault and print a line per tool call."""
        self.output_dir.mkdir(parents=True)
        for fault in faults:
            # A fresh world for each session: the fault to fake, an empty HR database, a new graph.
            os.environ["PTO_FAULT"] = fault
            HrDatabase.reset()
            graph: ProvenanceGraph = ProvenanceGraph.reset()

            answer: str = self.chat(self.PROMPT)

            # Save the whole graph, then report: the agent's final answer, each verdict, and the tamper check.
            graph.save(self.output_dir / f"{fault}.graph.json")
            self.logger.info("=== fault: %s ===", fault)
            self.logger.info("agent said: %s", answer.strip()[:300])
            for node in graph.nodes:
                if node.get("kind") == "verification":
                    data: dict[str, Any] = node.get("data")
                    self.logger.info("verdict: %s  problems: %s", data.get("verdict"), data.get("problems"))
            self.logger.info("tool calls never verified: %d", len(graph.pending()))
            self.logger.info("graph intact against anchor: %s", graph.intact(anchor=AnchorLog.latest(graph.run_id)))
        self.logger.info("Graphs saved in %s", self.output_dir)

    def chat(self, prompt: str) -> str:
        """
        Send one message to the network and wait for its final answer (one turn, as in pilot_runner.py chat()).

        :return: The final answer the user would see.
        """
        session: AgentSession = AgentSessionFactory().create_session("direct", self.AGENT_NAME)
        input_processor: StreamingInputProcessor = StreamingInputProcessor(session=session)
        processor: BasicMessageProcessor = input_processor.get_message_processor()
        request: dict[str, Any] = input_processor.formulate_chat_request(prompt)
        for chat_response in session.streaming_chat(request):
            processor.process_message(chat_response.get("response", {}), chat_response.get("type"))
        return processor.get_compiled_answer() or ""

    @staticmethod
    def main() -> None:
        """Parse --faults, prepare the environment and run."""
        parser = argparse.ArgumentParser(description="Run the PTO network once per fault and print the verdicts.")
        parser.add_argument("--faults", nargs="+", choices=PtoRunner.FAULTS, default=list(PtoRunner.FAULTS))
        faults: list[str] = parser.parse_args().faults
        # The report is this runner's log at INFO, printed as plain lines.
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        runner = PtoRunner()
        runner.prepare_environment()
        runner.run(faults)


if __name__ == "__main__":
    PtoRunner.main()
