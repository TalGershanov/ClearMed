import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# "pragma once"
sys.modules["bootstrap"] = sys.modules[__name__]

if __name__ == "__main__":
	from convert_medline_xml_to_json import convert_to_clearmed_json
	from create_clearmed_db import create_database, populate_hebrew_translations
	from populate_hebrew_terms import populate_hebrew_terms

	convert_to_clearmed_json()
	create_database()
	populate_hebrew_terms()
	# Overwrite each 'he' row's placeholder short_explanation (copied
	# verbatim from English at scrape time) with a real translation -- must
	# run after populate_hebrew_terms(), since it depends on the 'he' rows
	# that step creates.
	populate_hebrew_translations()
