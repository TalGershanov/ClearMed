import json
from db import close_connection
from db import get_connection


def get_terms_for_trie():
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("""
        SELECT term, synonyms
        FROM medical_terms
    """)

    rows = cursor.fetchall()
    close_connection(cursor, connection)

    terms = []

    for row in rows:
        terms.append({
            "term": row["term"],
            "synonyms": json.loads(row["synonyms"])
        })

    return terms

def get_terms_details(terms):

    placeholders = ",".join(["?"] * len(terms))
    connection = get_connection()
    cursor = connection.cursor()

    query = f"""
        SELECT
            term,
            short_explanation,
            simple_explanation,
            synonyms,
            categories
        FROM medical_terms
        WHERE LOWER(term) IN ({placeholders})
    """

    cursor.execute(query, terms)
    rows = cursor.fetchall()
    close_connection(cursor, connection)

    results = []
    for row in rows:

        results.append({

            "term":
                row["term"],

            "short_explanation":
                row["short_explanation"],

            "simple_explanation":
                row["simple_explanation"],

            "synonyms":
                json.loads(row["synonyms"]),

            "categories":
                json.loads(row["categories"])
        })

    return results