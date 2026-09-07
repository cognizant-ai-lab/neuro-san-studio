"""Deterministic synthetic North American banking environment."""

from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from typing import Any
from typing import Dict

from coded_tools.fraud_defense.models import SyntheticEnvironment


BASE_TIME = datetime(2026, 1, 15, 14, 0, 0)
US_LOCATIONS = ["New York, NY", "Chicago, IL", "Dallas, TX", "Seattle, WA", "Atlanta, GA", "Toronto, ON"]
MERCHANTS = [
    ("M-COFFEE", "Northstar Coffee", "food"),
    ("M-HOME", "Harbor Home Supply", "home"),
    ("M-TRAVEL", "Continental Travel", "travel"),
    ("M-UTIL", "Civic Utilities", "utilities"),
    ("M-RETAIL", "Evergreen Retail", "retail"),
    ("M-HEALTH", "Bluebird Health", "health"),
]
SCENARIOS = [
    ("account_takeover", True),
    ("beneficiary_fraud", True),
    ("mule_network", True),
    ("coordinated_payment", True),
    ("card_anomaly", True),
    ("velocity_attack", True),
    ("device_anomaly", True),
    ("legitimate_high_value", False),
    ("legitimate_travel", False),
    ("false_positive", False),
]


def _transaction(
    transaction_id: str,
    case_id: str,
    customer_id: str,
    account_id: str,
    device_id: str,
    beneficiary_id: str,
    merchant_id: str,
    amount: float,
    timestamp: datetime,
    location: str,
    channel: str,
    event_type: str,
    campaign_id: str | None = None,
) -> Dict[str, Any]:
    """Create a normalized synthetic transaction record."""
    return {
        "transaction_id": transaction_id,
        "case_id": case_id,
        "customer_id": customer_id,
        "account_id": account_id,
        "device_id": device_id,
        "beneficiary_id": beneficiary_id,
        "merchant_id": merchant_id,
        "amount": round(amount, 2),
        "currency": "USD",
        "timestamp": timestamp.isoformat() + "Z",
        "location": location,
        "channel": channel,
        "event_type": event_type,
        "status": "posted",
        "campaign_id": campaign_id,
    }


def generate_environment(seed: int = 17, case_count: int = 600) -> SyntheticEnvironment:
    """Generate a realistic, seeded synthetic environment with hidden labels.

    The first case is always the flagship coordinated payment-fraud campaign so
    a live demo does not depend on random scenario placement. Remaining cases
    cycle through ambiguous legitimate and fraud scenarios.
    """
    if case_count < 1:
        raise ValueError("case_count must be positive")
    env = SyntheticEnvironment(seed=seed, generated_at="2026-01-15T14:00:00Z")
    env.merchants = [{"merchant_id": item[0], "name": item[1], "category": item[2]} for item in MERCHANTS]
    env.locations = [{"location_id": f"LOC-{index:02d}", "name": value, "country": "US" if ", ON" not in value else "CA"} for index, value in enumerate(US_LOCATIONS, 1)]
    env.policy_rules = [
        {"policy_id": "POL-HIGH-APPROVAL", "name": "High-risk approval", "rule": "HIGH and CRITICAL require human approval"},
        {"policy_id": "POL-CRITICAL-NOAUTO", "name": "Critical no autonomy", "rule": "CRITICAL cannot execute autonomously"},
        {"policy_id": "POL-SIM-FIRST", "name": "Simulation before deployment", "rule": "A control must be simulated before shadow deployment"},
        {"policy_id": "POL-SHADOW", "name": "Shadow first", "rule": "New controls start in SHADOW"},
    ]
    env.controls = [
        {"control_id": "BASE-001", "name": "Existing bank rules", "lifecycle": "ACTIVE", "scope": "baseline", "friction": "low"},
        {"control_id": "BASE-002", "name": "Known beneficiary screening", "lifecycle": "ACTIVE", "scope": "beneficiary", "friction": "low"},
    ]

    # Shared entities make campaign graph traversal meaningful.
    shared_campaign_accounts: Dict[str, list[str]] = {}
    shared_campaign_beneficiaries: Dict[str, str] = {}

    for index in range(case_count):
        case_id = f"CASE-{index + 1:04d}"
        customer_id = f"CUST-{index + 1:04d}"
        account_id = f"ACCT-{index + 1:04d}"
        device_id = f"DEV-{index + 1:04d}"
        scenario = "coordinated_payment" if index == 0 else SCENARIOS[(index - 1) % len(SCENARIOS)][0]
        fraud = scenario not in {"legitimate_high_value", "legitimate_travel", "false_positive"}
        campaign_id = None
        if fraud and scenario in {"mule_network", "coordinated_payment", "beneficiary_fraud"}:
            campaign_id = f"CMP-{1 + (index // 3):03d}"
            shared_campaign_accounts.setdefault(campaign_id, []).append(account_id)
            shared_campaign_beneficiaries.setdefault(campaign_id, f"BEN-MULE-{1 + (index // 3):03d}")

        customer = {
            "customer_id": customer_id,
            "display_name": f"Synthetic Customer {index + 1:04d}",
            "segment": "premium" if index % 11 == 0 else "consumer",
            "tenure_months": 18 + (index * 7) % 96,
            "home_location": US_LOCATIONS[index % len(US_LOCATIONS)],
            "preferred_channel": ["mobile", "web", "branch"][index % 3],
            "risk_band": ["standard", "standard", "enhanced"][index % 3],
        }
        account = {
            "account_id": account_id,
            "customer_id": customer_id,
            "account_type": "checking",
            "opened_at": (BASE_TIME - timedelta(days=customer["tenure_months"] * 30)).date().isoformat(),
            "average_balance": round(2500 + (index * 913) % 48000, 2),
        }
        device = {
            "device_id": device_id,
            "customer_id": customer_id,
            "device_type": ["iPhone", "Android", "WebBrowser"][index % 3],
            "first_seen": (BASE_TIME - timedelta(days=90 + (index % 170))).date().isoformat(),
            "trusted": scenario not in {"account_takeover", "device_anomaly", "coordinated_payment"},
        }
        env.customers.append(customer)
        env.accounts.append(account)
        env.devices.append(device)

        beneficiary_id = shared_campaign_beneficiaries.get(campaign_id, f"BEN-{index + 1:04d}") if campaign_id else f"BEN-{index + 1:04d}"
        env.beneficiaries.append({
            "beneficiary_id": beneficiary_id,
            "name": f"Synthetic Beneficiary {beneficiary_id.split('-')[-1]}",
            "country": "US" if index % 8 else "CA",
            "first_seen": (BASE_TIME - timedelta(days=2 if fraud else 120)).date().isoformat(),
            "risk_band": "elevated" if fraud and index % 2 == 0 else "standard",
        })

        # Ten history events establish customer behavior. Suspicious scenarios
        # are anomalous only in relation to this history, not by amount alone.
        history_count = 10 + (index % 6)
        for history_index in range(history_count):
            merchant_id, _, _ = MERCHANTS[(index + history_index) % len(MERCHANTS)]
            amount = 25 + ((index * 37 + history_index * 19) % 220)
            timestamp = BASE_TIME - timedelta(days=30 - history_index * 2, hours=index % 5)
            env.transactions.append(
                _transaction(
                    f"TX-H-{index + 1:04d}-{history_index:02d}", case_id, customer_id, account_id, device_id,
                    f"BEN-H-{index + 1:04d}", merchant_id, amount, timestamp,
                    customer["home_location"], customer["preferred_channel"], "historical_purchase"
                )
            )

        current_time = BASE_TIME - timedelta(minutes=index % 47)
        if index == 0:
            # Flagship: compromise → new beneficiary → test → dormant interval
            # → high-value transfer → connected-account movement.
            attacker_device = "DEV-ATTACK-001"
            env.devices.append({"device_id": attacker_device, "customer_id": customer_id, "device_type": "Android", "first_seen": "2026-01-15", "trusted": False})
            sequence = [
                ("TX-0001-01", 2.50, -48, "login", "New York, NY", "web", "session_start"),
                ("TX-0001-02", 1.00, -44, "p2p", "New York, NY", "mobile", "beneficiary_added"),
                ("TX-0001-03", 17.25, -40, "p2p", "New York, NY", "mobile", "test_transfer"),
                ("TX-0001-04", 48000.00, -15, "wire", "New York, NY", "mobile", "high_value_transfer"),
                ("TX-0001-05", 12500.00, -7, "wire", "Dallas, TX", "mobile", "connected_account_movement"),
            ]
            for tx_id, amount, minute_offset, channel_type, location, channel, event_type in sequence:
                env.transactions.append(_transaction(tx_id, case_id, customer_id, account_id, attacker_device, beneficiary_id, "M-RETAIL", amount, current_time + timedelta(minutes=minute_offset), location, channel, event_type, "CMP-001"))
            env.sessions.append({"session_id": "SES-0001-01", "customer_id": customer_id, "account_id": account_id, "device_id": attacker_device, "started_at": (current_time - timedelta(minutes=48)).isoformat() + "Z", "ip_region": "New York, NY", "mfa": "not_verified"})
            # Two connected destination accounts are represented as related
            # accounts and edges via their shared campaign beneficiary.
            for related_index in range(2):
                related_account = f"ACCT-MULE-{related_index + 1:03d}"
                env.accounts.append({"account_id": related_account, "customer_id": f"CUST-MULE-{related_index + 1:03d}", "account_type": "checking", "opened_at": "2025-06-01", "average_balance": 7800.0})
                env.customers.append({"customer_id": f"CUST-MULE-{related_index + 1:03d}", "display_name": f"Synthetic Mule {related_index + 1:03d}", "segment": "consumer", "tenure_months": 8, "home_location": "Dallas, TX", "preferred_channel": "mobile", "risk_band": "enhanced"})
        else:
            current_amount = 180 + ((index * 127) % 1000)
            current_device = device_id
            current_location = customer["home_location"]
            current_channel = customer["preferred_channel"]
            event_type = "purchase"
            if scenario == "account_takeover":
                current_device = f"DEV-NEW-{index + 1:04d}"
                env.devices.append({"device_id": current_device, "customer_id": customer_id, "device_type": "Android", "first_seen": "2026-01-14", "trusted": False})
                current_location = US_LOCATIONS[(index + 2) % len(US_LOCATIONS)]
                current_amount = 2200 + (index % 4) * 700
                event_type = "unusual_transfer"
            elif scenario == "beneficiary_fraud":
                current_amount = 1800 + (index % 5) * 850
                event_type = "new_beneficiary_transfer"
            elif scenario == "mule_network":
                current_amount = 900 + (index % 6) * 650
                event_type = "connected_account_movement"
            elif scenario == "coordinated_payment":
                current_amount = 700 + (index % 7) * 500
                event_type = "coordinated_transfer"
            elif scenario == "card_anomaly":
                current_amount = 350 + (index % 8) * 95
                current_location = US_LOCATIONS[(index + 3) % len(US_LOCATIONS)]
                event_type = "card_not_present"
            elif scenario == "velocity_attack":
                current_amount = 180 + (index % 3) * 30
                event_type = "rapid_payment"
            elif scenario == "device_anomaly":
                current_device = f"DEV-SHARED-{index % 9:02d}"
                current_amount = 900 + (index % 3) * 450
                event_type = "device_reuse"
            elif scenario == "legitimate_high_value":
                current_amount = 16000 + (index % 4) * 5000
                event_type = "home_purchase"
            elif scenario == "legitimate_travel":
                current_amount = 1200 + (index % 3) * 420
                current_location = "Toronto, ON" if index % 2 else "Chicago, IL"
                event_type = "travel_purchase"
            else:
                current_amount = 400 + (index % 5) * 50
                event_type = "routine_purchase_with_alert"
            env.transactions.append(_transaction(f"TX-{index + 1:04d}-01", case_id, customer_id, account_id, current_device, beneficiary_id, "M-TRAVEL" if event_type == "travel_purchase" else "M-RETAIL", current_amount, current_time, current_location, current_channel, event_type, campaign_id))
            if scenario == "velocity_attack":
                for burst_index in range(3):
                    env.transactions.append(_transaction(f"TX-{index + 1:04d}-B{burst_index + 1}", case_id, customer_id, account_id, current_device, beneficiary_id, "M-RETAIL", current_amount * 0.75, current_time + timedelta(minutes=burst_index * 3), current_location, current_channel, "rapid_payment", campaign_id))
            env.sessions.append({"session_id": f"SES-{index + 1:04d}-01", "customer_id": customer_id, "account_id": account_id, "device_id": current_device, "started_at": current_time.isoformat() + "Z", "ip_region": current_location, "mfa": "verified" if not fraud else "step_up_pending"})

        alert_transaction = next(tx for tx in reversed(env.transactions) if tx["case_id"] == case_id and not tx["event_type"].startswith("historical"))
        alert_score = round(min(0.99, 0.28 + (0.36 if fraud else 0.12) + ((index * 17) % 23) / 100), 3)
        env.alerts.append({"alert_id": f"ALT-{index + 1:04d}", "case_id": case_id, "transaction_id": alert_transaction["transaction_id"], "alert_type": "behavioral_anomaly", "triggered_at": alert_transaction["timestamp"], "initial_score": alert_score, "status": "open"})
        env.cases.append({
            "case_id": case_id,
            "customer_id": customer_id,
            "account_id": account_id,
            "alert_id": f"ALT-{index + 1:04d}",
            "priority": "critical" if index == 0 else ("high" if fraud else "medium"),
            "scenario": scenario,
            "campaign_id": campaign_id,
            "opened_at": alert_transaction["timestamp"],
            "status": "open",
            "ground_truth": {"fraud": fraud, "scenario": scenario, "campaign_id": campaign_id, "loss_at_risk": round(sum(tx["amount"] for tx in env.transactions if tx["case_id"] == case_id and not tx["event_type"].startswith("historical")), 2)},
        })
        env.investigator_actions.append({"action_id": f"ACT-{index + 1:04d}-01", "case_id": case_id, "actor": "alert_engine", "action": "opened_case", "timestamp": alert_transaction["timestamp"]})

    env.campaigns = []
    for campaign_id, account_ids in sorted(shared_campaign_accounts.items()):
        if campaign_id == "CMP-001":
            account_ids = account_ids + ["ACCT-MULE-001", "ACCT-MULE-002"]
        env.campaigns.append({"campaign_id": campaign_id, "campaign_type": "coordinated payment fraud", "account_ids": account_ids, "beneficiary_id": shared_campaign_beneficiaries[campaign_id], "status": "active"})
    return env
