"""Test script for the Lesson Illustration feature in Study Book mode."""
import sys
sys.path.insert(0, 'backend')
from services.docx_generator import DocxGenerator

# Sample lesson illustrations
lesson_illustrations = [
    {
        "topic": "Quadratic Equations",
        "introduction": "A quadratic equation is a polynomial equation of degree 2. The general form is ax^2 + bx + c = 0 where a != 0.",
        "key_concepts": [
            {"name": "Standard Form", "definition": "ax^2 + bx + c = 0 where a, b, c are real numbers and a != 0"},
            {"name": "Discriminant", "definition": "The value b^2 - 4ac determines the nature of roots"},
            {"name": "Roots", "definition": "The values of x that satisfy the equation (also called solutions or zeros)"}
        ],
        "theorems": [
            {"name": "Quadratic Formula", "statement": "For ax^2 + bx + c = 0, the solutions are given by the quadratic formula", "notation": "x = frac(-b +- sqrt(b^2 - 4ac), 2a)"},
            {"name": "Sum and Product of Roots", "statement": "If r1 and r2 are roots, then r1 + r2 = -b/a and r1 * r2 = c/a", "notation": ""}
        ],
        "key_formulas": [
            {"name": "Quadratic Formula", "formula": "x = frac(-b +- sqrt(b^2 - 4ac), 2a)", "description": "General solution for any quadratic equation"},
            {"name": "Difference of Squares", "formula": "a^2 - b^2 = (a-b)(a+b)", "description": "Factoring pattern"}
        ],
        "important_notes": [
            "The coefficient a must not equal zero, otherwise it is a linear equation",
            "If the discriminant b^2 - 4ac < 0, the equation has no real solutions",
            "Always check your solutions by substituting back into the original equation"
        ]
    },
    {
        "topic": "Similarity",
        "introduction": "Two geometric figures are similar if they have the same shape but not necessarily the same size.",
        "key_concepts": [
            {"name": "Similar Triangles", "definition": "Triangles with equal corresponding angles and proportional corresponding sides"},
            {"name": "Scale Factor", "definition": "The ratio of corresponding sides between similar figures"}
        ],
        "theorems": [
            {"name": "AA Similarity", "statement": "If two angles of one triangle are equal to two angles of another, the triangles are similar", "notation": ""},
            {"name": "Euclidean Theorem", "statement": "In a right triangle with altitude to hypotenuse, each leg is the geometric mean of the hypotenuse and its adjacent segment", "notation": "(AB)^2 = BC * BD"}
        ],
        "key_formulas": [
            {"name": "Ratio of Areas", "formula": "frac(A_1, A_2) = (frac(s_1, s_2))^2", "description": "Area ratio equals the square of the scale factor"}
        ],
        "important_notes": [
            "Similar figures have equal angles but proportional sides",
            "The order of vertices matters when writing similarity statements"
        ]
    }
]

# Sample solved examples
solved_examples = [
    {
        "title": "Find in R the solution set of: x^2 - 6x - 11 = 0",
        "topic": "Quadratic Equations",
        "difficulty": "medium",
        "solution_steps": ["x^2 - 6x - 11 = 0", "x = frac(6 +- sqrt(80), 2)", "S.S. = {7, -1}"],
        "key_formula": "x = frac(-b +- sqrt(b^2 - 4ac), 2a)",
        "coefficients": {"a": "1", "b": "-6", "c": "-11"}
    }
]

# Sample exercises
exercises = [
    {
        "question": "Solve 4x^2 + 40x + 100 = 0",
        "type": "multiple_choice",
        "options": ["x = -5", "x = 1", "x = -1", "x = 5"],
        "correct_answer": "x = -5",
        "topic": "Quadratic Equations",
        "difficulty": "medium",
        "hint": "Factor as perfect square."
    },
    {
        "question": "In triangle ABC, if AD perpendicular BC, then (AB)^2 = BC * ___",
        "type": "fill_in_blank",
        "options": [],
        "correct_answer": "BD",
        "topic": "Similarity",
        "difficulty": "easy",
        "hint": "Euclidean theorem"
    }
]

config = {
    "title": "1st Secondary Math - Study Book",
    "target_pages": 10,
    "density": "standard",
    "school_name": "Test School",
    "year": "2024-2025",
    "language": "en",
    "output_mode": "illustration_and_workbook"
}

output_path = "backend/data/workbooks/test_lesson_illustration.docx"

generator = DocxGenerator(
    config=config,
    exercises=exercises,
    output_path=output_path,
    illustration_content=solved_examples,
    lesson_illustrations=lesson_illustrations,
    num_pages=10
)

result = generator.generate()
print(f"Generated: {result}")
print("SUCCESS - Study book with lesson illustrations created!")
