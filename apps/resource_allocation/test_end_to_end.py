from tools.skill_matcher import evaluate_candidates as evaluate_skills
from tools.experience_assessor import evaluate_candidates as evaluate_experience
from tools.availability_assessor import evaluate_candidates as evaluate_availability
from tools.candidate_ranker import rank_candidates

required_skills = [
    "Python",
    "Azure",
    "GenAI"
]

required_experience = 4

candidates = [
    {
        "name": "Ravi",
        "skills": ["Python", "Azure", "GenAI"],
        "experience": 5,
        "availability": 80
    },
    {
        "name": "Kiran",
        "skills": ["Python", "GenAI"],
        "experience": 2,
        "availability": 90
    }
]

candidates = evaluate_skills(required_skills, candidates)
candidates = evaluate_experience(required_experience, candidates)
candidates = evaluate_availability(candidates)
candidates = rank_candidates(candidates)

for candidate in candidates:
    print(candidate)