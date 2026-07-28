import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Imports must stay inside this guard: convert_medline_xml_to_json/create_clearmed_db
# both `import bootstrap` for the sys.path side effect above, so when this file runs as
# __main__ and imports them here, Python loads this same file a second time under the
# module name "bootstrap". Module-level imports would make that second load re-enter
# this same import, crashing with a partial-init ImportError. Only run as
# `python server_init/bootstrap.py`; `python -m server_init.bootstrap` is not supported.
if __name__ == "__main__":
	from convert_medline_xml_to_json import convert_to_clearmed_json
	from create_clearmed_db import create_database

	convert_to_clearmed_json()
	create_database()
