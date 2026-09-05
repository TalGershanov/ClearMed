from unittest.mock import MagicMock, patch

from logic.translator import apply_translations, build_explanation_map, simplify_text_with_openai


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


def test_build_explanation_map_includes_approved_term_with_explanation():
	detected = [_term("34", "High Blood Pressure", 0, 10, short_explanation="explanation")]
	explanation_map, explained = build_explanation_map(detected, {"34": True}, "short_explanation")
	assert explanation_map == {"High Blood Pressure": "explanation"}
	assert explained == ["High Blood Pressure"]


def test_build_explanation_map_dedupes_same_concept_by_term_name():
	detected = [
		_term("7", "Abdominal Pain", 0, 10, short_explanation="pain in the belly"),
		_term("7", "Abdominal Pain", 20, 30, short_explanation="pain in the belly"),
	]
	explanation_map, explained = build_explanation_map(detected, {"7": True}, "short_explanation")
	assert explanation_map == {"Abdominal Pain": "pain in the belly"}
	assert explained == ["Abdominal Pain"]


def test_build_explanation_map_skips_unapproved_term():
	detected = [_term("34", "High Blood Pressure", 0, 10, short_explanation="explanation")]
	explanation_map, explained = build_explanation_map(detected, {"34": False}, "short_explanation")
	assert explanation_map == {}
	assert explained == []


def test_build_explanation_map_skips_missing_explanation():
	detected = [_term("34", "High Blood Pressure", 0, 10, short_explanation=None)]
	explanation_map, explained = build_explanation_map(detected, {"34": True}, "short_explanation")
	assert explanation_map == {}
	assert explained == []


def _mock_openai_response(text):
	response = MagicMock()
	response.choices = [MagicMock(message=MagicMock(content=text))]
	return response


def test_simplify_text_with_openai_returns_rewritten_text_on_success():
	mock_client = MagicMock()
	mock_client.chat.completions.create.return_value = _mock_openai_response("Rewritten patient-friendly text.")
	with patch("logic.translator._get_openai_client", return_value=mock_client):
		result = simplify_text_with_openai("Original text.", {"term": "explanation"})
	assert result == "Rewritten patient-friendly text."


def test_simplify_text_with_openai_falls_back_to_original_on_failure():
	mock_client = MagicMock()
	mock_client.chat.completions.create.side_effect = RuntimeError("API down")
	with patch("logic.translator._get_openai_client", return_value=mock_client):
		result = simplify_text_with_openai("Original text.", {"term": "explanation"})
	assert result == "Original text."


def test_simplify_text_with_openai_skips_api_call_when_no_explanations():
	with patch("logic.translator._get_openai_client") as mock_get_client:
		result = simplify_text_with_openai("Original text.", {})
	assert result == "Original text."
	mock_get_client.assert_not_called()
