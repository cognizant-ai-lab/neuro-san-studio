"""Optional direct Neuro-SAN invocation for narrative-only assistance."""

import json
import logging
from pathlib import Path

from apps.broker_submission_readiness.models import ReadinessReport

LOGGER = logging.getLogger(__name__)
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class NeuroSanNarrativeClient:
    """Invoke the registered network while preserving Python-owned readiness."""

    def __init__(self, agent_name: str = "industry/broker_submission_readiness") -> None:
        self.agent_name = agent_name

    def generate_narrative(self, report: ReadinessReport) -> str:
        """Ask Neuro-SAN agents for narrative text; never consume a model decision."""
        from neuro_san.client.agent_session_factory import DirectAgentSessionFactory
        from neuro_san_studio.commands.project_environment import ProjectEnvironment

        ProjectEnvironment(str(REPOSITORY_ROOT)).apply()
        session = DirectAgentSessionFactory().create_session(
            agent_name=self.agent_name,
            use_direct=True,
            metadata={"application": "broker_submission_readiness"},
        )
        report_context = {
            "policy_number": report["policy"]["policy_number"],
            "insured_name": report["policy"]["insured_name"],
            "readiness_status": report["readiness_status"],
            "readiness_source": report["readiness_source"],
            "missing_fields": report["missing_fields"],
            "missing_documents": report["missing_documents"],
            "field_errors": report["field_errors"],
            "material_changes": report["material_changes"],
            "summary": report["summary"],
        }
        user_message = (
            "Create a concise supplemental submission summary, rule explanation, and broker follow-up draft "
            "from this JSON. The readiness_status is already computed by deterministic Python rules. "
            "Do not change or reinterpret it. This is not an underwriting, pricing, acceptance, or rejection task. "
            "Do not send or claim to send any email.\n\n"
            + json.dumps(report_context, indent=2)
        )

        response_text = ""
        for message in session.streaming_chat({"user_message": {"text": user_message}}):
            response = message.get("response")
            if isinstance(response, dict) and isinstance(response.get("text"), str):
                response_text = response["text"]
            if message.get("done") is True:
                break
        if not response_text.strip():
            raise RuntimeError("Neuro-SAN completed without returning narrative text.")
        LOGGER.info("Neuro-SAN generated supplemental narrative for %s", report["policy"]["policy_number"])
        return response_text
