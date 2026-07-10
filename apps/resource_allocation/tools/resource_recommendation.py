def generate_recommendations(candidates):

    recommendations = []

    for candidate in candidates:

        recommendation = {
            "rank": candidate["rank"],
            "name": candidate["name"],
            "final_score": candidate["final_score"],
            "skills": candidate["skills"],
            "experience": candidate["experience"],
            "availability": candidate["availability"]
        }

        recommendations.append(recommendation)

    return recommendations
def print_recommendations(candidates):

    print("\nRecommended Resources\n")

    for candidate in candidates:

        print(f"Rank: {candidate['rank']}")
        print(f"Name: {candidate['name']}")
        print(f"Final Score: {candidate['final_score']}")
        print(f"Skills: {', '.join(candidate['skills'])}")
        print(f"Experience: {candidate['experience']} Years")
        print(f"Availability: {candidate['availability']}%")
        print("-" * 40)
if __name__ == "__main__":

    candidates = [
        {
            "rank": 1,
            "name": "Ravi",
            "skills": ["Python", "Azure", "GenAI"],
            "experience": 5,
            "availability": 80,
            "final_score": 96
        },
        {
            "rank": 2,
            "name": "Kiran",
            "skills": ["Python", "GenAI"],
            "experience": 2,
            "availability": 90,
            "final_score": 66.34
        }
    ]

    recommendations = generate_recommendations(candidates)

    print_recommendations(recommendations)