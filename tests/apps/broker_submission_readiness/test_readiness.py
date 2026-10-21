"""Tests for the deterministic broker submission readiness business rules."""

from pathlib import Path

import pytest
from pyhocon import ConfigFactory

from apps.broker_submission_readiness.consistency import compare_submission
from apps.broker_submission_readiness.demo_scenarios import DEMO_SCENARIOS
from apps.broker_submission_readiness.demo_scenarios import get_demo_scenario
from apps.broker_submission_readiness.policy_repository import PolicyNotFoundError
from apps.broker_submission_readiness.policy_repository import get_policy
from apps.broker_submission_readiness.readiness import decide_readiness
from apps.broker_submission_readiness.service import analyze_submission
from coded_tools.industry.broker_submission_readiness.readiness_tools import ReadinessDecisionTool
from coded_tools.industry.broker_submission_readiness.readiness_tools import SubmissionValidationTool

ROOT = Path(__file__).resolve().parents[3]


def test_complete_demo_is_ready_for_underwriter_review_only() -> None:
    report = analyze_submission(get_demo_scenario("Complete submission"))

    assert report["readiness_status"] == "READY FOR UNDERWRITER REVIEW"
    assert report["readiness_source"] == "deterministic_python_business_rules"
    assert report["missing_fields"] == []
    assert report["missing_documents"] == []
    assert report["material_changes"] == []
    assert report["underwriting_decision_made"] is False
    assert "not an underwriting" in report["summary"]


def test_missing_demo_needs_information_and_identifies_exact_gaps() -> None:
    report = analyze_submission(get_demo_scenario("Missing information"))

    assert report["readiness_status"] == "NEEDS INFORMATION"
    assert report["missing_fields"] == ["Business description"]
    assert report["missing_documents"] == [
        "ACORD 126 liability section",
        "Currently valued loss runs",
        "Property/location schedule",
    ]
    assert report["field_errors"] == ["Annual revenue must be a positive whole-dollar amount."]
    assert "MISSING_REQUIRED_FIELDS" in report["triggered_rules"]
    assert "MISSING_REQUIRED_DOCUMENTS" in report["triggered_rules"]
    assert "INVALID_FIELD_VALUES" in report["triggered_rules"]
    assert "Please correct the following items" in report["email_draft"]["body"]
    assert report["material_changes"] == []


def test_material_demo_is_complete_but_flags_changes_for_human_review() -> None:
    report = analyze_submission(get_demo_scenario("Material changes"))

    assert report["readiness_status"] == "READY FOR UNDERWRITER REVIEW"
    assert report["missing_fields"] == []
    assert report["missing_documents"] == []
    assert len(report["material_changes"]) == 4
    assert "BUSINESS_DESCRIPTION_CHANGED" in report["triggered_rules"]
    assert "MAILING_ADDRESS_CHANGED" in report["triggered_rules"]
    assert "ANNUAL_REVENUE_MATERIAL_CHANGE" in report["triggered_rules"]
    assert "REQUESTED_LIMIT_MATERIAL_CHANGE" in report["triggered_rules"]


def test_unknown_policy_fails_explicitly() -> None:
    with pytest.raises(PolicyNotFoundError):
        get_policy("POL-DOES-NOT-EXIST")


def test_readiness_tool_uses_rule_result_not_agent_opinion() -> None:
    result = ReadinessDecisionTool().invoke(
        {"missing_fields": [], "missing_documents": [], "field_errors": []}, {}
    )

    assert result["readiness_status"] == "READY FOR UNDERWRITER REVIEW"
    assert result["readiness_source"] == "deterministic_python_business_rules"
    assert result["underwriting_decision_made"] is False


def test_validation_coded_tool_reports_gaps() -> None:
    submission = get_demo_scenario("Missing information")
    result = SubmissionValidationTool().invoke(
        {"policy_number": submission["policy_number"], "submission": submission}, {}
    )

    assert "error" not in result
    assert result["missing_fields"] == ["Business description"]
    assert result["missing_documents"] == [
        "ACORD 126 liability section",
        "Currently valued loss runs",
        "Property/location schedule",
    ]


def test_readiness_tool_rejects_malformed_lists() -> None:
    result = ReadinessDecisionTool().invoke(
        {"missing_fields": "none", "missing_documents": [], "field_errors": []}, {}
    )

    assert result == {
        "error": "missing_fields, missing_documents, and field_errors must be string lists."
    }


def test_email_draft_requires_human_review_and_is_not_sent() -> None:
    report = analyze_submission(get_demo_scenario("Missing information"))

    assert report["human_review_required"] is True
    assert "No email is sent" not in report["email_draft"]["body"]
    assert "This request concerns submission completeness only" in report["email_draft"]["body"]


def test_materiality_threshold_and_text_normalization() -> None:
    policy = get_policy("POL-1001")
    submission = get_demo_scenario("Complete submission")
    submission["business_description"] = "  COMMERCIAL   PRINTING AND OFFICE STATIONERY PRODUCTION "
    submission["annual_revenue"] = 1_199_999

    comparisons = compare_submission(policy, submission)
    revenue = next(item for item in comparisons if item["field"] == "Annual revenue")
    description = next(item for item in comparisons if item["field"] == "Business description")

    assert revenue["changed"] is True
    assert revenue["material"] is False
    assert description["changed"] is False


def test_materiality_threshold_uses_exact_whole_dollar_comparison() -> None:
    policy = get_policy("POL-1001")
    submission = get_demo_scenario("Complete submission")
    submission["annual_revenue"] = 1_200_000

    revenue = next(
        item for item in compare_submission(policy, submission) if item["field"] == "Annual revenue"
    )

    assert revenue["changed"] is True
    assert revenue["material"] is True


def test_validation_tool_rejects_policy_number_mismatch() -> None:
    submission = get_demo_scenario("Complete submission")
    result = SubmissionValidationTool().invoke(
        {"policy_number": "POL-2002", "submission": submission}, {}
    )

    assert result == {"error": "policy_number and a correctly shaped submission object are required."}


def test_hocon_is_parseable_and_registered() -> None:
    network_path = ROOT / "registries" / "industry" / "broker_submission_readiness.hocon"
    manifest_path = ROOT / "registries" / "industry" / "manifest.hocon"
    network = ConfigFactory.parse_string(
        network_path.read_text(encoding="utf-8"),
        basedir=str(ROOT),
        resolve=False,
    )
    manifest = ConfigFactory.parse_string(
        manifest_path.read_text(encoding="utf-8"),
        basedir=str(ROOT),
        resolve=False,
    )

    assert len(network["tools"]) == 12
    assert network["llm_config"]["class"] == "openrouter"
    assert network["llm_config"]["model_name"] == "openai/gpt-5.2"
    assert manifest['"industry/broker_submission_readiness.hocon"'] is True
    tool_classes = {
        tool["name"]: tool["class"]
        for tool in network["tools"]
        if "class" in tool
    }
    assert tool_classes == {
        "PolicyLookupTool": "readiness_tools.PolicyLookupTool",
        "SubmissionValidationTool": "readiness_tools.SubmissionValidationTool",
        "ConsistencyCheckTool": "readiness_tools.ConsistencyCheckTool",
        "ReadinessDecisionTool": "readiness_tools.ReadinessDecisionTool",
    }
    assert set(DEMO_SCENARIOS) == {
        "Complete submission",
        "Missing information",
        "Material changes",
    }


def test_decision_status_depends_only_on_completeness_inputs() -> None:
    assert decide_readiness([], [], []) == ("READY FOR UNDERWRITER REVIEW", [])
    status, rules = decide_readiness([], [], ["bad annual revenue"])
    assert status == "NEEDS INFORMATION"
    assert rules == ["INVALID_FIELD_VALUES"]
