import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# "pragma once"
sys.modules["bootstrap"] = sys.modules[__name__]

if __name__ == "__main__":
	from convert_medline_xml_to_json import convert_to_clearmed_json
	from create_clearmed_db import create_database

	convert_to_clearmed_json()
	create_database()
