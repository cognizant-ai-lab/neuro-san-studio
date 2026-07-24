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

import logging
from os import environ
from time import perf_counter
from typing import Any
from typing import Dict

from neuro_san.interfaces.agent_progress_reporter import AgentProgressReporter
from neuro_san.internals.interfaces.context_type_toolbox_factory import ContextTypeToolboxFactory
from neuro_san.internals.run_context.factory.master_toolbox_factory import MasterToolboxFactory

from coded_tools.agent_network_editor.and_logger import AndLogger
from coded_tools.agent_network_editor.connectivity_dictionary_converter import ConnectivityDictionaryConverter
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_DEFINITION
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_NAME
from coded_tools.agent_network_editor.constants import PROGRESS_HANDLER
from coded_tools.agent_network_editor.constants import PROGRESS_HANDLER_LOCK
from coded_tools.agent_network_editor.constants import TOOLBOX_FACTORY
from coded_tools.agent_network_editor.constants import TOOLBOX_FACTORY_LOCK
from coded_tools.agent_network_editor.sly_data_lock import SlyDataLock


class ProgressHandler:
    """
    Common handler for progress during the building of agent networks
    """

    PROGRESS_THROTTLE_SECONDS: float = 5.0

    def __init__(self):
        """
        Constructor
        """
        # Timestamp (per perf_counter()) of the last progress report actually sent.
        # Initialized to -inf so the very first report is always allowed through:
        # perf_counter()'s epoch is unspecified (on most platforms it is "seconds
        # since boot"), so initializing to 0.0 could wrongly throttle the first
        # report of a process that starts less than PROGRESS_THROTTLE_SECONDS
        # after that epoch.
        self.last_progress: float = float("-inf")

        # When the throttle suppresses a report, we stash the reporter that would
        # have been used so the final state can still be flushed at the end of the
        # agent run (see flush_pending()). None means nothing is pending.
        #
        # Only the reporter is stashed, not the report payload: at flush time the
        # latest AGENT_NETWORK_DEFINITION is re-read from sly_data, so the flush
        # always sends the freshest state and the (potentially expensive)
        # connectivity conversion is paid only once no matter how many reports
        # were suppressed in between.
        self.pending_reporter: AgentProgressReporter = None

    def should_report(self, force: bool = False) -> bool:
        """
        Should the progress be reported?

        This is a "leading edge" throttle: a report arriving inside the throttle
        window is dropped, not delayed. Callers that get False back are expected
        to record the drop on pending_reporter so that flush_pending() can send
        the final state at the end of the run.

        :param force: When True, bypass the throttle window entirely.
                The send time is still recorded so subsequent throttled callers
                back off relative to this send.
        :return: True if the report should be sent
        """
        now: float = perf_counter()
        if not force and now - self.last_progress <= self.PROGRESS_THROTTLE_SECONDS:
            return False

        self.last_progress = now
        return True

    @staticmethod
    async def report_progress(
        args: dict[str, Any],
        sly_data: Dict[str, Any],
        network_definition: dict[str, Any],
        name: str = None,
        force: bool = False,
    ):
        """
        Common handler for progress during the building of agent networks.

        Reports are throttled to at most one per PROGRESS_THROTTLE_SECONDS per
        sly_data instance. A report suppressed by the throttle is not lost for
        good: its reporter is stashed on the ProgressHandler and the latest
        network state is sent by flush_pending() when the agent loop exits
        normally (from AgentNetworkDefinitionMiddleware.aafter_agent()).
        Without that, a build whose last edit lands inside the throttle window
        would leave the client's progress view one or two edits stale.

        Sending is best-effort: a failure inside the send is logged and the
        reporter is re-stashed for the end-of-run flush, so a broken progress
        report can never fail the tool or model call that triggered it.

        :param args: The arguments dictionary for the calling CodedTool.
                Expected to contain a "progress_reporter" entry; without one
                there is nothing to send through and the call is a no-op.
        :param sly_data: The sly_data dictionary on which the throttling state
                (ProgressHandler) and the ToolboxFactory cache are kept.
                Required — every caller has one, and reporting without it would
                silently skip both the throttle and the cache.
        :param network_definition: The network definition dictionary
        :param name: The name of the agent network. If None, will not be reported in progress.
        :param force: When True, bypass the throttle and always send.
                Used by AgentNetworkDefinitionMiddleware of the top-level designer,
                whose reports fire at most once per designer model call — far less
                frequently than the editor tools in the subnetworks — and which is
                what guarantees the client sees the fully merged network state
                (including subnetwork edits whose own reports were throttled)
                before each designer model call.
        """
        progress_reporter: AgentProgressReporter = args.get("progress_reporter")
        if progress_reporter is None:
            # Nothing to send through. Checked before any throttle bookkeeping so
            # a reporter-less call can never consume the throttle slot or clobber
            # a stashed pending reporter. (neuro-san always injects a reporter
            # into coded tool args, so this is unreachable today.)
            return

        async with await SlyDataLock.get_lock(sly_data, PROGRESS_HANDLER_LOCK):
            progress_handler: ProgressHandler = sly_data.get(PROGRESS_HANDLER)
            if progress_handler is None:
                progress_handler = ProgressHandler()
                sly_data[PROGRESS_HANDLER] = progress_handler

            if not progress_handler.should_report(force=force):
                # Throttled. Remember the reporter so flush_pending() can send
                # the final state at the end of the run. The payload is *not*
                # remembered — flush_pending() re-reads the latest definition
                # from sly_data (see comment in __init__).
                progress_handler.pending_reporter = progress_reporter
                return

            # We are sending now, so any previously suppressed report is
            # superseded by this one (which carries same-or-newer state).
            progress_handler.pending_reporter = None

        try:
            await ProgressHandler._send_report(progress_reporter, sly_data, network_definition, name)
        except Exception as exception:  # pylint: disable=broad-exception-caught
            # Best-effort telemetry: a failed send (toolbox file I/O, connectivity
            # conversion, journal write on a closed stream) must not fail the tool
            # or model call that triggered it. Re-stash the reporter so the
            # end-of-run flush retries with the freshest state; last_progress
            # stays advanced so the throttle window is respected either way.
            logger = AndLogger(logging.getLogger(ProgressHandler.__name__))
            logger.error("Progress report failed; deferring to end-of-run flush: %s", exception)
            async with await SlyDataLock.get_lock(sly_data, PROGRESS_HANDLER_LOCK):
                progress_handler = sly_data.get(PROGRESS_HANDLER)
                # Only re-stash if nothing newer was stashed (or sent) meanwhile.
                if progress_handler is not None and progress_handler.pending_reporter is None:
                    progress_handler.pending_reporter = progress_reporter

    @staticmethod
    async def flush_pending(sly_data: Dict[str, Any]):
        """
        Send the last throttled progress report, if any.

        Called when the agent loop exits normally
        (AgentNetworkDefinitionMiddleware.aafter_agent()) while the request — and
        therefore the stashed reporter's journal — is still alive. This ensures
        the client ends up seeing the final network state even when the report
        for the last edit fell inside the throttle window and was dropped.
        Note the limit of that guarantee: if the run aborts on an unhandled
        error, the after-agent hooks never execute and a throttled final report
        stays dropped — same as the pre-throttle-fix behavior.

        The report goes out through the reporter stashed from the suppressed tool
        call, so from the client's perspective it originates from the same tool as
        every other progress report. This is what lets the (by design)
        reporter-less subnetwork middleware flush without creating a duplicate
        progress stream of its own.

        :param sly_data: The sly_data dictionary holding the throttling state.
                May be None, in which case there is nothing to flush.
        """
        if sly_data is None:
            return

        pending_reporter: AgentProgressReporter = None
        async with await SlyDataLock.get_lock(sly_data, PROGRESS_HANDLER_LOCK):
            progress_handler: ProgressHandler = sly_data.get(PROGRESS_HANDLER)
            if progress_handler is None or progress_handler.pending_reporter is None:
                # Either nothing was ever reported on this sly_data, or the most
                # recent report went out unthrottled — the client is up to date.
                return

            pending_reporter = progress_handler.pending_reporter
            progress_handler.pending_reporter = None
            # Count the flush as a send to keep the throttle bookkeeping
            # consistent for any later reports on this sly_data.
            progress_handler.last_progress = perf_counter()

        # Re-read the freshest state from sly_data rather than replaying the payload
        # of the suppressed call: several edits may have been throttled since the
        # reporter was stashed, and we only want to pay for one conversion/report
        # carrying the final state.
        #
        # Only a dict is sendable. An empty dict is a legitimate final state
        # (e.g. the last agent was just removed) and MUST go out — dropping it
        # would leave the client showing agents that no longer exist. A missing
        # definition or a non-dict shape (the persistence middleware can rewrite
        # this sly_data key to a connectivity-style list at end of run) cannot be
        # converted and is skipped.
        network_definition: dict[str, Any] = sly_data.get(AGENT_NETWORK_DEFINITION)
        if not isinstance(network_definition, dict):
            return

        try:
            await ProgressHandler._send_report(
                pending_reporter, sly_data, network_definition, sly_data.get(AGENT_NETWORK_NAME)
            )
        except Exception as exception:  # pylint: disable=broad-exception-caught
            # Best-effort: this hook runs as a langgraph node, and an exception
            # escaping it would replace the run's real final answer with an error
            # message after the network was already successfully built (e.g. when
            # the client disconnected and the outgoing queue is already shut down).
            logger = AndLogger(logging.getLogger(ProgressHandler.__name__))
            logger.error("Final progress flush failed: %s", exception)

    @staticmethod
    async def _send_report(
        progress_reporter: AgentProgressReporter,
        sly_data: Dict[str, Any],
        network_definition: dict[str, Any],
        name: str = None,
    ):
        """
        Format the network definition per AGENT_NETWORK_DESIGNER_PROGRESS_STYLE and send it.

        This is the unthrottled sending path shared by report_progress() and
        flush_pending(). Throttling decisions and error containment are the
        callers' responsibility; both callers guarantee a non-None reporter
        and sly_data.

        :param progress_reporter: The AgentProgressReporter to send the progress through
        :param sly_data: The sly_data dictionary used for the ToolboxFactory cache
        :param network_definition: The network definition dictionary
        :param name: The name of the agent network. If None, will not be reported in progress.
        """
        use_key: str = AGENT_NETWORK_DEFINITION
        use_network_definition: dict[str, Any] | list[dict[str, Any]] = network_definition

        agent_progress_style: str = environ.get("AGENT_NETWORK_DESIGNER_PROGRESS_STYLE", "internal")
        if agent_progress_style == "connectivity":
            # The idea here is that a multi-user MAUI server can turn on this env variable
            # so that agent network progress is converted to connectivity-style data format
            # that it already knows how to render.  Using the different key name allows the AGENT_PROGRESS
            # dictionary to look just like a ConnectivityResponse from the service.

            # Get a cached toolbox factory so we don't have to read info from a file every time
            toolbox_factory: ContextTypeToolboxFactory = sly_data.get(TOOLBOX_FACTORY)
            if toolbox_factory is None:
                async with await SlyDataLock.get_lock(sly_data, TOOLBOX_FACTORY_LOCK):
                    toolbox_factory: ContextTypeToolboxFactory = sly_data.get(TOOLBOX_FACTORY)
                    if toolbox_factory is None:
                        # DEF - not sure if this empty dict is good enough
                        empty: Dict[str, Any] = {}
                        toolbox_factory: ContextTypeToolboxFactory = MasterToolboxFactory.create_toolbox_factory(empty)
                        toolbox_factory.load()
                        sly_data[TOOLBOX_FACTORY] = toolbox_factory

            # Do the conversion
            use_key: str = "connectivity_info"
            converter = ConnectivityDictionaryConverter(toolbox_factory=toolbox_factory)
            use_network_definition = converter.from_dict(network_definition)

        elif agent_progress_style == "internal":
            # Report the internal structure used by Agent Network Designer and pals.
            # This is what was used in the first iterations with nsflow.
            use_key: str = AGENT_NETWORK_DEFINITION
            use_network_definition: dict[str, Any] = network_definition

        progress: dict[str, Any] = {
            # Agent network definition with an added agent
            use_key: use_network_definition
        }

        # Optionally add agent network name
        if name:
            progress[AGENT_NETWORK_NAME] = name

        await progress_reporter.async_report_progress(progress)
