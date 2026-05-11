import json
import sqlite3
import re


JSON_FILE = "output/clearmed_terms_english.json"
DB_FILE = "clearmed.db"

def create_short_explanation(full_explanation, max_words=30):
    if not full_explanation:
        return None

    # מסירים מקור כמו NIH וכו'
    text = re.sub(r"NIH:.*", "", full_explanation).strip()

    # מפצלים למשפטים
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return None

    cleaned_sentences = []

    for sentence in sentences:
        lower_sentence = sentence.lower().strip()

        # מדלגים על משפטי שאלה שלא מסבירים כלום
        if lower_sentence.startswith("what is "):
            continue

        if lower_sentence.startswith("what are "):
            continue

        if lower_sentence.startswith("what causes "):
            continue

        if lower_sentence.startswith("who is "):
            continue

        if lower_sentence.startswith("who are "):
            continue

        if lower_sentence.startswith("how is "):
            continue

        if lower_sentence.startswith("how are "):
            continue

        cleaned_sentences.append(sentence)

    # אם הסינון מחק הכל, חוזרים למשפטים המקוריים
    if cleaned_sentences:
        sentences = cleaned_sentences

    priority_keywords = [
        "measures",
        "used to",
        "means",
        "is a",
        "is an",
        "are a",
        "are an",
        "refers to",
        "is the",
        "are the"
    ]

    chosen_sentence = None

    for keyword in priority_keywords:
        for sentence in sentences[:6]:
            if keyword in sentence.lower():
                chosen_sentence = sentence
                break

        if chosen_sentence is not None:
            break

    # אם לא מצאנו לפי keywords, ניקח את המשפט הראשון שנשאר אחרי סינון השאלות
    if chosen_sentence is None:
        chosen_sentence = sentences[0]

    words = chosen_sentence.split()

    if len(words) > max_words:
        chosen_sentence = " ".join(words[:max_words]) + "..."

    return chosen_sentence.strip()

def create_tables(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS medical_terms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT,
            term TEXT NOT NULL,
            simple_explanation TEXT,
            short_explanation TEXT, 
            synonyms TEXT,
            categories TEXT
        )
    """)


def insert_terms(cursor, terms):
    for item in terms:

        simple_explanation = item.get("simple_explanation")

        short_explanation = create_short_explanation(
            simple_explanation
        )

        cursor.execute("""
            INSERT INTO medical_terms (
                source_id,
                term,
                short_explanation,
                simple_explanation,
                synonyms,
                categories
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            item.get("source_id"),

            item.get("term"),

            short_explanation,

            simple_explanation,

            json.dumps(
                item.get("synonyms", []),
                ensure_ascii=False
            ),

            json.dumps(
                item.get("categories", []),
                ensure_ascii=False
            )
        ))

def create_database():
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    terms = data["terms"]

    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()

    cursor.execute("DROP TABLE IF EXISTS medical_terms")
    create_tables(cursor)

    cursor.execute("DELETE FROM medical_terms")

    insert_terms(cursor, terms)

    connection.commit()
    connection.close()

    print(f"Database created: {DB_FILE}")
    print(f"Inserted terms: {len(terms)}")


if __name__ == "__main__":
    create_database()