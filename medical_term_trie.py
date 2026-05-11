import sqlite3
import json
import re


DB_FILE = "clearmed.db"

def normalize_text(text):
    """
    מנרמל טקסט כדי שהחיפוש יהיה אחיד.

    למשל:
    'HbA1C,'  -> 'hba1c'
    'Type-2 Diabetes' -> 'type 2 diabetes'
    """

    # הופך לאותיות קטנות
    text = text.lower()

    # מוחק סימני פיסוק
    text = re.sub(r"[^a-z0-9\s]", " ", text)

    # מסדר רווחים
    text = re.sub(r"\s+", " ", text).strip()

    return text


def tokenize(text):
    """
    מחלק טקסט לרשימת מילים.
    """

    return normalize_text(text).split()


class TrieNode:
    """
    כל Node בעץ מייצג מילה אחת.

    למשל:
    type -> 2 -> diabetes
    """

    def __init__(self):

        # מילון:
        # word -> next TrieNode
        self.children = {}

        # האם זה סוף של term חוקי?
        self.is_end = False

        # אם זה סוף term:
        # מה המונח הראשי?
        #
        # לדוגמה:
        # HbA1C -> main_term = A1C
        self.main_term = None


class MedicalTermTrie:

    def __init__(self):

        # root הוא ההתחלה של כל העץ
        self.root = TrieNode()

    def insert(self, phrase, main_term):
        """
        מכניס phrase לתוך העץ.

        phrase:
        'type 2 diabetes'

        main_term:
        'Type 2 Diabetes'
        """

        # מפצל למילים
        words = tokenize(phrase)

        # אם phrase ריק
        if not words:
            return

        # מתחילים מהשורש
        current = self.root

        # עוברים מילה מילה
        for word in words:

            # אם עדיין אין child כזה
            # יוצרים node חדש
            if word not in current.children:
                current.children[word] = TrieNode()

            # יורדים level בעץ
            current = current.children[word]

        # מסמנים שזה סוף term
        self.is_end = True

        current.is_end = True

        # שומרים מה ה-main medical term
        current.main_term = main_term

    def find_terms(self, text):
        """
        מקבל טקסט חופשי
        ומחזיר אילו מושגים רפואיים נמצאו.
        """

        words = tokenize(text)

        found_terms = []

        # i = מאיפה מתחילים לחפש בטקסט
        i = 0

        while i < len(words):

            # מתחילים כל חיפוש מחדש מה-root
            current = self.root

            # נשמור את ה-match הכי ארוך שמצאנו
            longest_match = None

            # עד איפה ה-match הגיע
            longest_match_end = i

            # j מתקדם קדימה בטקסט
            j = i

            """
            מנסים להתקדם בעץ כל עוד:
            המילה הבאה קיימת כ-child
            """

            while j < len(words) and words[j] in current.children:

                # יורדים לעומק הבא בעץ
                current = current.children[words[j]]

                """
                אם הגענו לסוף term חוקי
                נשמור אותו.
                """

                if current.is_end:

                    matched_text = " ".join(words[i:j + 1])

                    longest_match = {
                        "matched_text": matched_text,

                        # המונח הראשי במסד הנתונים
                        "main_term": current.main_term,

                        # איפה התחיל בטקסט
                        "start_word_index": i,

                        # איפה נגמר בטקסט
                        "end_word_index": j
                    }

                    longest_match_end = j

                # ממשיכים לבדוק אם יש term ארוך יותר
                j += 1

            """
            אם מצאנו match:
            ניקח את הארוך ביותר.
            """

            if longest_match:

                found_terms.append(longest_match)

                # מדלגים קדימה
                # כדי לא לזהות terms חופפים
                i = longest_match_end + 1

            else:
                # אם לא מצאנו term
                # מתקדמים מילה אחת
                i += 1

        return found_terms


def load_terms_from_db():
    """
    טוען את כל המונחים מה-DB.
    """

    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()

    cursor.execute("""
        SELECT term, synonyms
        FROM medical_terms
    """)

    rows = cursor.fetchall()

    connection.close()

    return rows


def build_trie_from_db():
    """
    בונה Trie מכל המונחים הרפואיים.
    """

    trie = MedicalTermTrie()

    rows = load_terms_from_db()

    for term, synonyms_json in rows:

        # מכניסים את המונח הראשי
        trie.insert(term, term)

        # טוענים synonyms מה-JSON
        synonyms = json.loads(synonyms_json)

        # מכניסים גם synonyms
        for synonym in synonyms:
            trie.insert(synonym, term)

    return trie


if __name__ == "__main__":

    # בונים Trie מה-database
    trie = build_trie_from_db()

    sample_text = """
    The patient has type 2 diabetes and his HbA1C test was high.
    The doctor also mentioned blood glucose levels.
    """

    # מחפשים מושגים רפואיים בטקסט
    results = trie.find_terms(sample_text)

    print("Found medical terms:\n")

    for result in results:
        print(result)