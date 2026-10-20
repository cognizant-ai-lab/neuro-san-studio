"""Synthetic examples used by the Streamlit demo and tests."""

from copy import deepcopy

from apps.broker_submission_readiness.models import Submission

DEMO_SCENARIOS: dict[str, Submission] = {
    "Complete submission": {
        "policy_number": "POL-1001",
        "business_name": "Northstar Printworks LLC",
        "business_description": "Commercial printing and office stationery production",
        "mailing_address": "1200 Market Street, Columbus, OH 43215",
        "annual_revenue": 1_000_000,
        "requested_limit": 2_000_000,
        "broker_name": "Jordan Lee",
        "broker_email": "jordan.lee@example.test",
        "documents": ["acord_125", "acord_126", "loss_runs", "property_schedule"],
    },
    "Missing information": {
        "policy_number": "POL-1001",
        "business_name": "Northstar Printworks LLC",
        "business_description": "",
        "mailing_address": "1200 Market Street, Columbus, OH 43215",
        "annual_revenue": 0,
        "requested_limit": 2_000_000,
        "broker_name": "Jordan Lee",
        "broker_email": "jordan.lee@example.test",
        "documents": ["acord_125"],
    },
    "Material changes": {
        "policy_number": "POL-1001",
        "business_name": "Northstar Printworks LLC",
        "business_description": "Commercial printing plus packaging and fulfillment",
        "mailing_address": "4300 East Broad Street, Columbus, OH 43213",
        "annual_revenue": 1_500_000,
        "requested_limit": 2_400_000,
        "broker_name": "Jordan Lee",
        "broker_email": "jordan.lee@example.test",
        "documents": ["acord_125", "acord_126", "loss_runs", "property_schedule"],
    },
}


def get_demo_scenario(name: str) -> Submission:
    """Return a defensive copy of a named synthetic scenario."""
    try:
        return deepcopy(DEMO_SCENARIOS[name])
    except KeyError as error:
        raise ValueError(f"Unknown demo scenario: {name}") from error
