"""Streamlit interface for the Neuro-SAN broker submission readiness demo."""

import logging
from pathlib import Path
import sys

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.broker_submission_readiness.demo_scenarios import DEMO_SCENARIOS
from apps.broker_submission_readiness.demo_scenarios import get_demo_scenario
from apps.broker_submission_readiness.models import ReadinessReport
from apps.broker_submission_readiness.models import Submission
from apps.broker_submission_readiness.policy_repository import PolicyNotFoundError
from apps.broker_submission_readiness.policy_repository import load_policies
from apps.broker_submission_readiness.service import analyze_submission
from apps.broker_submission_readiness.validation import DOCUMENT_LABELS
from apps.broker_submission_readiness.validation import FIELD_LABELS

LOGGER = logging.getLogger(__name__)
POLICIES = load_policies()
DOCUMENT_OPTIONS = list(DOCUMENT_LABELS)


def _email_text(report: ReadinessReport) -> str:
    """Return the complete draft as plain text for the gated copy display."""
    draft = report["email_draft"]
    return f"Subject: {draft['subject']}\n\n{draft['body']}"


def _render_report(report: ReadinessReport) -> None:
    """Render deterministic findings and human-review controls."""
    st.subheader("Deterministic readiness result")
    if report["readiness_status"] == "NEEDS INFORMATION":
        st.warning(f"**{report['readiness_status']}** — missing intake information; not an underwriting decision.")
    else:
        st.success(
            f"**{report['readiness_status']}** — completeness only; not an underwriting decision or acceptance."
        )

    st.caption(f"Status source: `{report['readiness_source']}`")
    st.markdown("**Submission summary**")
    st.write(report["summary"])

    left, right = st.columns(2)
    with left:
        st.markdown("**Missing required fields**")
        st.write(report["missing_fields"] or "None")
        if report["field_errors"]:
            st.markdown("**Input errors**")
            st.write(report["field_errors"])
    with right:
        st.markdown("**Missing required documents**")
        st.write(report["missing_documents"] or "None")

    st.markdown("**Existing policy vs. submitted values**")
    st.dataframe(report["comparisons"], use_container_width=True, hide_index=True)

    st.markdown("**Material changes for human underwriter review**")
    st.write(report["material_changes"] or "None identified by the configured deterministic rules.")

    st.markdown("**Triggered business rules**")
    if report["triggered_rules"]:
        for rule, explanation in zip(report["triggered_rules"], report["rule_explanations"], strict=True):
            st.write(f"- `{rule}` — {explanation}")
    else:
        st.write("No missing-information rules were triggered.")

    st.info(
        "This tool checks intake completeness and flags differences only. "
        "It does not perform underwriting, pricing, acceptance, rejection, or risk selection."
    )


def _render_email_review(report: ReadinessReport) -> None:
    """Require explicit human review before presenting a copyable email draft."""
    st.subheader("Broker follow-up draft")
    st.caption("No email is sent. Review the draft below, then approve it before the copyable version is shown.")
    st.text(f"Subject: {report['email_draft']['subject']}")
    st.text(report["email_draft"]["body"])

    reviewed = st.checkbox(
        "I have reviewed this draft and confirm it is appropriate to copy.",
        key="broker_email_reviewed",
    )
    if st.button("Approve draft for copying", disabled=not reviewed, key="approve_broker_email"):
        st.session_state["broker_email_approved"] = True

    if st.session_state.get("broker_email_approved", False):
        st.success("Human review recorded. The message remains a draft; no email was sent.")
        st.code(_email_text(report), language="text")


def main() -> None:
    """Start the interactive submission review workflow."""
    st.set_page_config(page_title="Neuro-SAN Broker Submission Readiness Checker", layout="wide")
    st.title("Neuro-SAN Broker Submission Readiness Checker")
    st.write(
        "Check broker submission completeness against a synthetic policy record. "
        "The result is not an underwriting or pricing decision."
    )
    st.warning("DEMO MODE — synthetic data only. Do not enter real policyholder or broker information.")

    scenario_name = st.selectbox("Demo scenario", list(DEMO_SCENARIOS))
    if st.button("Load selected demo scenario"):
        st.session_state.update(get_demo_scenario(scenario_name))
        st.session_state.pop("readiness_report", None)
        st.session_state.pop("broker_email_approved", None)
        st.session_state.pop("broker_email_reviewed", None)
        st.rerun()

    st.subheader("Submission information")
    with st.form("submission_form"):
        policy_numbers = list(POLICIES)
        saved_policy = st.session_state.get("policy_number", policy_numbers[0])
        policy_default = saved_policy if saved_policy in policy_numbers else policy_numbers[0]
        policy_index = policy_numbers.index(policy_default)
        policy_number = st.selectbox("Policy number", policy_numbers, index=policy_index, key="policy_number")

        column_one, column_two = st.columns(2)
        with column_one:
            business_name = st.text_input(
                FIELD_LABELS["business_name"],
                value=st.session_state.get("business_name", ""),
                key="business_name",
            )
            business_description = st.text_area(
                FIELD_LABELS["business_description"],
                value=st.session_state.get("business_description", ""),
                key="business_description",
            )
            mailing_address = st.text_input(
                FIELD_LABELS["mailing_address"],
                value=st.session_state.get("mailing_address", ""),
                key="mailing_address",
            )
            annual_revenue = st.number_input(
                FIELD_LABELS["annual_revenue"],
                min_value=0,
                step=10_000,
                value=int(st.session_state.get("annual_revenue", 0)),
                key="annual_revenue",
            )
        with column_two:
            requested_limit = st.number_input(
                FIELD_LABELS["requested_limit"],
                min_value=0,
                step=100_000,
                value=int(st.session_state.get("requested_limit", 0)),
                key="requested_limit",
            )
            broker_name = st.text_input(
                FIELD_LABELS["broker_name"],
                value=st.session_state.get("broker_name", ""),
                key="broker_name",
            )
            broker_email = st.text_input(
                FIELD_LABELS["broker_email"],
                value=st.session_state.get("broker_email", ""),
                key="broker_email",
            )
            documents = st.multiselect(
                "Documents supplied",
                DOCUMENT_OPTIONS,
                default=st.session_state.get("documents", []),
                format_func=lambda document: DOCUMENT_LABELS[document],
                key="documents",
            )

        submitted = st.form_submit_button("Check submission readiness")

    if submitted:
        submission: Submission = {
            "policy_number": policy_number,
            "business_name": business_name,
            "business_description": business_description,
            "mailing_address": mailing_address,
            "annual_revenue": int(annual_revenue),
            "requested_limit": int(requested_limit),
            "broker_name": broker_name,
            "broker_email": broker_email,
            "documents": list(documents),
        }
        try:
            report = analyze_submission(submission)
        except PolicyNotFoundError as error:
            LOGGER.warning("Unable to retrieve selected synthetic policy: %s", error)
            st.error(str(error))
        else:
            st.session_state["readiness_report"] = report
            st.session_state.pop("broker_email_approved", None)
            st.session_state.pop("broker_email_reviewed", None)

    report = st.session_state.get("readiness_report")
    if isinstance(report, dict):
        _render_report(report)
        _render_email_review(report)


if __name__ == "__main__":
    main()
