import json


def load_employees():
    with open(
        "apps/resource_allocation/data/employees.json",
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def find_candidates(requirements):
    employees = load_employees()

    matches = []

    required_skills = set(
        requirements.get("skills", [])
    )

    required_experience = requirements.get(
        "experience", 0
    )

    required_availability = requirements.get(
        "availability", 0
    )

    for employee in employees:

        employee_skills = set(
            employee.get("skills", [])
        )

        matched_skills = required_skills.intersection(
            employee_skills
        )

        skill_match_percentage = (
            len(matched_skills)
            / len(required_skills)
        ) * 100 if required_skills else 0

        experience_match = (
            employee.get("experience", 0)
            >= required_experience
        )

        availability_match = (
            employee.get("availability", 0)
            >= required_availability
        )

        # Must have at least one matching skill
        skill_match = len(matched_skills) > 0

        if (
            skill_match
            and experience_match
            and availability_match
        ):

            candidate = employee.copy()

            candidate["matched_skills"] = list(
                matched_skills
            )

            candidate["skill_match_percentage"] = round(
                skill_match_percentage,
                2
            )

            matches.append(candidate)

    matches.sort(
        key=lambda x: x["skill_match_percentage"],
        reverse=True
    )

    return matches


if __name__ == "__main__":
# Temporary test data2
# Later this will come from Requirement Analyzer Agent
    requirements = {
        "skills": [
            "SAP S/4HANA",
            "SAP Fiori"
        ],
        "experience": 4,
        "availability": 50
    }

    results = find_candidates(
        requirements
    )

    print(
        json.dumps(
            results,
            indent=4
        )
    )