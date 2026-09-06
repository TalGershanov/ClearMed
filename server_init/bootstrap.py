import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# "pragma once"
sys.modules["bootstrap"] = sys.modules[__name__]

if __name__ == "__main__":
	from log_config import setup_logging
	from build_db import build_database

	setup_logging()
	build_database()
