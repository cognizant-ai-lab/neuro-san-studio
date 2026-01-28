import json
from coded_tools.factory_sense.medic.remedy import MedicTool

t = MedicTool()  # will attempt to download sop.txt from S3
result = t._generate_remedy(
    machine_id="test-machine",
    issue_type="temperature_high",
    severity="warning",
    current_metrics={"temperature": 45},
    recommended_actions=["Check cooling fan"],
    trend_analysis={"last_1h": "rising"},
    root_cause_analysis={"suspected": "blocked_filter"},
    safety_considerations=["Wear gloves"]
)
print(json.dumps(result, indent=2))