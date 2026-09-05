import json
import os
import tempfile


def load_jsonl(path):
	records = []
	if os.path.exists(path):
		with open(path, "r", encoding="utf-8") as f:
			for line in f:
				line = line.strip()
				if line:
					records.append(json.loads(line))
	return records


def write_jsonl_atomic(path, records):
	directory = os.path.dirname(path)
	os.makedirs(directory, exist_ok=True)
	fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
	try:
		with os.fdopen(fd, "w", encoding="utf-8") as f:
			for record in records:
				f.write(json.dumps(record, ensure_ascii=False) + "\n")
			f.flush()
			os.fsync(f.fileno())
		os.replace(tmp_path, path)
	except Exception:
		if os.path.exists(tmp_path):
			os.remove(tmp_path)
		raise


def load_json(path, default):
	if os.path.exists(path):
		with open(path, "r", encoding="utf-8") as f:
			return json.load(f)
	return default


def write_json_atomic(path, data):
	directory = os.path.dirname(path)
	os.makedirs(directory, exist_ok=True)
	fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
	try:
		with os.fdopen(fd, "w", encoding="utf-8") as f:
			json.dump(data, f, ensure_ascii=False, indent=2)
			f.flush()
			os.fsync(f.fileno())
		os.replace(tmp_path, path)
	except Exception:
		if os.path.exists(tmp_path):
			os.remove(tmp_path)
		raise
