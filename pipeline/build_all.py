from convert_medline_xml_to_json import convert_to_clearmed_json
from create_clearmed_db import create_database

if __name__ == "__main__":
	convert_to_clearmed_json()
	create_database()
