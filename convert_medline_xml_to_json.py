import xml.etree.ElementTree as ET
import json
import re
from html import unescape


XML_FILE = "health_topics.xml"
JSON_FILE = "output/clearmed_terms_english.json"


def clean_html(raw_html):
    if not raw_html:
        return None

    text = unescape(raw_html)

    text = re.sub(r"<[^>]+>", " ", text)

    text = re.sub(r"\s+", " ", text).strip()

    return text if text else None


def get_text(element):
    if element is None:
        return None

    text = "".join(element.itertext()).strip()
    return text if text else None


def parse_topic_for_clearmed(topic):
    language = topic.get("language")

    # פילטר: רק מושגים באנגלית
    if language != "English":
        return None

    term = topic.get("title")

    synonyms = []
    for also_called in topic.findall("also-called"):
        text = get_text(also_called)
        if text:
            synonyms.append(text)

    categories = []
    for group in topic.findall("group"):
        text = get_text(group)
        if text:
            categories.append(text)

    raw_summary = get_text(topic.find("full-summary"))

    return {
        "source_id": topic.get("id"),
        "term": term,
        "synonyms": synonyms,
        "short_description": topic.get("meta-desc"),
        "simple_explanation": clean_html(raw_summary),
        "categories": categories
    }


def convert_to_clearmed_json():
    tree = ET.parse(XML_FILE)
    root = tree.getroot()

    clean_terms = []

    for topic in root.findall("health-topic"):
        parsed = parse_topic_for_clearmed(topic)

        if parsed is not None:
            clean_terms.append(parsed)

    output = {
        "source": "MedlinePlus Health Topic XML",
        "language": "English",
        "total_terms": len(clean_terms),
        "terms": clean_terms
    }

    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Done! Created {JSON_FILE}")
    print(f"Total English terms: {len(clean_terms)}")


if __name__ == "__main__":
    convert_to_clearmed_json()