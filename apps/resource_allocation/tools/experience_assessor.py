def calculate_experience_score(required_experience, candidate_experience):

    if required_experience <= 0:
        return 100

    score = (
        min(candidate_experience, required_experience)
        / required_experience
    ) * 100

    return round(score, 2)
def evaluate_candidates(required_experience, candidates):

    results = []

    for candidate in candidates:

        experience_score = calculate_experience_score(
            required_experience,
            candidate["experience"]
        )

        candidate_result = {
            **candidate,
            "experience_score": experience_score
        }

        results.append(candidate_result)

    return results
if __name__ == "__main__":

    required_experience = 4

    candidates = [
        {
            "name": "Ravi",
            "experience": 5
        },
        {
            "name": "Kiran",
            "experience": 2
        }
    ]

    result = evaluate_candidates(
        required_experience,
        candidates
    )

    print(result)