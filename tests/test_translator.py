from logic.translator import apply_translations


def _term(main_term, term_name, start, end, **explanations):
	return {"main_term": main_term, "term_name": term_name, "start": start, "end": end, **explanations}


def test_splices_at_detected_span_even_with_fused_hebrew_prefix():
	# "בלחץ" fuses the prefix "ב" onto "לחץ" with no space -- the detector's
	# own span (unlike an independent regex re-search for the bare term_name)
	# already covers the whole fused token correctly, so apply_translations
	# just has to trust it.
	text = "סבל בלחץ דם גבוה."
	start = text.index("בלחץ")
	end = start + len("בלחץ דם גבוה")
	detected = [_term("34", "לחץ דם גבוה", start, end, simple_explanation="הסבר בעברית")]
	translated, explained = apply_translations(text, detected, {"34": True}, "simple_explanation")
	assert translated == f"{text[:end]} (הסבר בעברית){text[end:]}"
	assert explained == ["לחץ דם גבוה"]


def test_two_occurrences_of_same_concept_both_spliced_and_deduplicated():
	text = "abdominal pain then more abdominal pain"
	first_start = text.index("abdominal pain")
	first_end = first_start + len("abdominal pain")
	second_start = text.rindex("abdominal pain")
	second_end = second_start + len("abdominal pain")
	detected = [
		_term("7", "Abdominal Pain", first_start, first_end, short_explanation="pain in the belly"),
		_term("7", "Abdominal Pain", second_start, second_end, short_explanation="pain in the belly"),
	]
	translated, explained = apply_translations(text, detected, {"7": True}, "short_explanation")
	assert translated.count("(pain in the belly)") == 2
	assert explained == ["Abdominal Pain"]


def test_unapproved_term_is_skipped():
	text = "high blood pressure"
	detected = [_term("34", "High Blood Pressure", 0, len(text), short_explanation="explanation")]
	translated, explained = apply_translations(text, detected, {"34": False}, "short_explanation")
	assert translated == text
	assert explained == []


def test_missing_explanation_is_skipped_not_spliced_as_none():
	text = "high blood pressure"
	detected = [_term("34", "High Blood Pressure", 0, len(text), short_explanation=None)]
	translated, explained = apply_translations(text, detected, {"34": True}, "short_explanation")
	assert translated == text
	assert "(None)" not in translated
	assert explained == []
