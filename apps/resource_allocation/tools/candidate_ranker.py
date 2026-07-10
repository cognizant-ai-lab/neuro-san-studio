def calculate_final_score(
    skill_match_score,
    experience_score,
    availability_score
):

    final_score = (
        (0.5 * skill_match_score) +
        (0.3 * experience_score) +
        (0.2 * availability_score)
    )

    return round(final_score, 2)
def rank_candidates(candidates):

    ranked_candidates = []

    for candidate in candidates:

        final_score = calculate_final_score(
            candidate["skill_match_score"],
            candidate["experience_score"],
            candidate["availability_score"]
        )

        candidate_result = {
            **candidate,
            "final_score": final_score
        }

        ranked_candidates.append(candidate_result)

    ranked_candidates.sort(
        key=lambda x: x["final_score"],
        reverse=True
    )

    return ranked_candidates
if __name__ == "__main__":

    candidates = [
        {
            "name": "Ravi",
            "skill_match_score": 100,
            "experience_score": 100,
            "availability_score": 80
        },
        {
            "name": "Kiran",
            "skill_match_score": 66.67,
            "experience_score": 50,
            "availability_score": 90
        }
    ]

    result = rank_candidates(candidates)

    print(result)