import sys
sys.path.insert(0, 'backend')
from services.docx_generator import DocxGenerator

# Sample solved examples (what the LLM would generate)
solved_examples = [
    {
        "title": "Find in R the solution set of: x^2 - 6x - 11 = 0 (given sqrt(5) ≈ 2)",
        "topic": "Quadratic Equations",
        "difficulty": "medium",
        "solution_steps": [
            "∵ x^2 - 6x - 11 = 0",
            "∵ x = frac(-b ± sqrt(b^2 - 4ac), 2a)",
            "∴ x = frac(6 ± sqrt(36 + 44), 2) = frac(6 ± sqrt(80), 2) = frac(6 ± 4sqrt(5), 2)",
            "∴ x_1 = frac(6 + 4sqrt(5), 2) = frac(6 + 8, 2) = 7",
            "or x_2 = frac(6 - 4sqrt(5), 2) = frac(6 - 8, 2) = -1",
            "∴ The S.S. = {7, -1}"
        ],
        "key_formula": "x = frac(-b ± sqrt(b^2 - 4ac), 2a)",
        "coefficients": {"a": "1", "b": "-6", "c": "-11"}
    },
    {
        "title": "Solve: 4x^2 - 25 = 0",
        "topic": "Quadratic Equations",
        "difficulty": "easy",
        "solution_steps": [
            "∵ 4x^2 - 25 = 0",
            "∴ (2x - 5)(2x + 5) = 0",
            "∴ x = frac(5, 2) or x = frac(-5, 2)",
            "∴ The S.S. = {frac(5,2), frac(-5,2)}"
        ],
        "key_formula": "a^2 - b^2 = (a-b)(a+b)",
        "coefficients": {}
    }
]

# Sample exercises
exercises = [
    {
        "question": "Solve the equation 4x^2 + 40x + 100 = 0 by factoring.",
        "type": "multiple_choice",
        "options": ["x = -5", "x = 1 or x = 25", "x = -1 or x = -25", "x = 5"],
        "correct_answer": "x = -5",
        "topic": "Quadratic Equations",
        "difficulty": "medium",
        "hint": "Factor the left side as a perfect square trinomial."
    },
    {
        "question": "Find the solution set of x(x - 19) = -15x in R.",
        "type": "multiple_choice",
        "options": ["{4}", "{0, 4}", "{-4}", "{19, -15}"],
        "correct_answer": "{4}",
        "topic": "Quadratic Equations",
        "difficulty": "easy",
        "hint": "Move all terms to one side and factor."
    },
    {
        "question": "In triangle ABC right-angled at A, if AD ⊥ BC, then (AB)^2 = BC × _____.",
        "type": "fill_in_blank",
        "options": [],
        "correct_answer": "BD",
        "topic": "Similarity",
        "difficulty": "easy",
        "hint": "Apply the Euclidean theorem."
    }
]

config = {
    "title": "1st Secondary Math Workbook",
    "target_pages": 8,
    "density": "standard",
    "school_name": "Futures Language Schools",
    "year": "2024-2025",
    "language": "en",
    "output_mode": "illustration_and_workbook"
}

output_path = "backend/data/workbooks/test_study_book.docx"

generator = DocxGenerator(
    config=config,
    exercises=exercises,
    output_path=output_path,
    illustration_content=solved_examples,
    num_pages=8
)

result = generator.generate()
print(f"Generated study book: {result}")
print("SUCCESS - Study book with solved examples created!")
