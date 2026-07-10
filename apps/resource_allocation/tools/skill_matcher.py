def calculate_skill_match(required_skills, candidate_skills):

    required = {s.lower() for s in required_skills}
    candidate = {s.lower() for s in candidate_skills}

    matched = required.intersection(candidate)

    score = (len(matched) / len(required)) * 100 if required else 0

    return {
        "matched_skills": list(matched),
        "matched_count": len(matched),
        "total_required": len(required),
        "skill_match_score": round(score, 2)
    }
def evaluate_candidates(required_skills, candidates):

    results = []

    for candidate in candidates:

        match_result = calculate_skill_match(
            required_skills,
            candidate["skills"]
        )

        candidate_result = {
            **candidate,
            **match_result
        }

        results.append(candidate_result)

    return results
if __name__ == "__main__":

    required_skills = [
        "Python",
        "Azure",
        "GenAI"
    ]

    candidates = [
        {
            "name": "Ravi",
            "skills": ["Python", "Azure", "GenAI"]
        },
        {
            "name": "Kiran",
            "skills": ["Python", "GenAI"]
        }
    ]

    result = evaluate_candidates(
        required_skills,
        candidates
    )

    print(result)