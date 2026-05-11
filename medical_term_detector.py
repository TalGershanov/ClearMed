import sqlite3
import json

from medical_term_trie import build_trie_from_db


DB_FILE = "clearmed.db"

def get_term_details(main_term):
    """
    מקבלת שם מונח ראשי, למשל A1C,
    ומחזירה את המידע עליו מה-DB.
    """

    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            term,
            short_explanation,
            simple_explanation,
            synonyms,
            categories
        FROM medical_terms
        WHERE LOWER(term) = LOWER(?)
    """, (main_term,))

    row = cursor.fetchone()

    connection.close()

    if row is None:
        return None

    return {
        "term": row[0],

        # ההסבר הקצר שיצרנו לבד
        "short_explanation": row[1],

        # ההסבר המלא מהמאגר
        "simple_explanation": row[2],

        "synonyms": json.loads(row[3]),

        "categories": json.loads(row[4])
    }


def detect_terms_with_explanations(text):
    """
    מזהה מושגים רפואיים בטקסט
    ומחזירה אותם יחד עם ההסברים מה-DB.
    """

    trie = build_trie_from_db()

    detected_terms = trie.find_terms(text)

    results = []

    for detected in detected_terms:
        details = get_term_details(detected["main_term"])

        if details:
            results.append({
                "matched_text": detected["matched_text"],
                "main_term": detected["main_term"],
                "start_word_index": detected["start_word_index"],
                "end_word_index": detected["end_word_index"],
                "short_description": details["short_description"],
                "simple_explanation": details["simple_explanation"],
                "categories": details["categories"],
                "synonyms": details["synonyms"]
            })

    return results


if __name__ == "__main__":
    sample_text = """
    The patient has HbA1C above normal range.
    The doctor mentioned blood glucose and type 2 diabetes.
    """

    results = detect_terms_with_explanations(sample_text)

    print("Detected medical terms:\n")

    for item in results:
        print("Matched text:", item["matched_text"])
        print("Main term:", item["main_term"])
        print("Explanation:", item["simple_explanation"])
        print("Categories:", item["categories"])
        print("-" * 50)