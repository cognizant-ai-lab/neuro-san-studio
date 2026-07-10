def calculate_availability_score(availability):

    if availability < 0:
        availability = 0

    if availability > 100:
        availability = 100

    return round(availability, 2)
def evaluate_candidates(candidates):

    results = []

    for candidate in candidates:

        availability_score = calculate_availability_score(
            candidate["availability"]
        )

        candidate_result = {
            **candidate,
            "availability_score": availability_score
        }

        results.append(candidate_result)

    return results
if __name__ == "__main__":

    candidates = [
        {
            "name": "Ravi",
            "availability": 80
        },
        {
            "name": "Kiran",
            "availability": 90
        },
        {
            "name": "Priya",
            "availability": 60
        }
    ]

    result = evaluate_candidates(candidates)

    print(result)
