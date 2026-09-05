from webapp.folders.service import DEFAULT_FOLDER_NAMES

from tests.conftest import register_and_login


def _create_folder(client, name, parent_folder_id=None, **extra):
	payload = {"name": name, "parent_folder_id": parent_folder_id, **extra}
	resp = client.post("/folders", json=payload)
	assert resp.status_code == 201, resp.text
	return resp.json()


def test_default_folders_created_on_registration(client):
	register_and_login(client, "newuser@example.com")
	resp = client.get("/folders")
	assert resp.status_code == 200
	names = {f["name"] for f in resp.json()}
	assert names == set(DEFAULT_FOLDER_NAMES)
	assert all(f["parent_folder_id"] is None for f in resp.json())


def test_create_root_folder(client):
	register_and_login(client, "user@example.com")
	folder = _create_folder(client, "Vaccinations")
	assert folder["name"] == "Vaccinations"
	assert folder["parent_folder_id"] is None
	assert folder["color"] is None
	assert folder["cover_image_path"] is None


def test_create_nested_folder(client):
	register_and_login(client, "user@example.com")
	parent = _create_folder(client, "Imaging Root", None)
	child = _create_folder(client, "2025 Scans", parent["id"])
	assert child["parent_folder_id"] == parent["id"]


def test_list_root_folders_excludes_nested(client):
	register_and_login(client, "user@example.com")
	before = client.get("/folders").json()
	parent = _create_folder(client, "Parent")
	_create_folder(client, "Child", parent["id"])

	after = client.get("/folders").json()
	# +1 for the new root "Parent"; the nested "Child" must not appear here
	assert len(after) == len(before) + 1
	assert "Child" not in [f["name"] for f in after]


def test_get_folder_returns_children_and_empty_documents(client):
	register_and_login(client, "user@example.com")
	parent = _create_folder(client, "Parent")
	child = _create_folder(client, "Child", parent["id"])

	resp = client.get(f"/folders/{parent['id']}")
	assert resp.status_code == 200
	body = resp.json()
	assert body["id"] == parent["id"]
	assert [c["id"] for c in body["children"]] == [child["id"]]
	assert body["documents"] == []


def test_rename_folder(client):
	register_and_login(client, "user@example.com")
	folder = _create_folder(client, "Old Name")
	resp = client.patch(f"/folders/{folder['id']}", json={"name": "New Name"})
	assert resp.status_code == 200
	assert resp.json()["name"] == "New Name"


def test_recolor_folder(client):
	register_and_login(client, "user@example.com")
	folder = _create_folder(client, "Colorful")
	resp = client.patch(f"/folders/{folder['id']}", json={"color": "#E07B55"})
	assert resp.status_code == 200
	assert resp.json()["color"] == "#E07B55"


def test_reparent_folder(client):
	register_and_login(client, "user@example.com")
	parent_a = _create_folder(client, "Parent A")
	parent_b = _create_folder(client, "Parent B")
	child = _create_folder(client, "Movable", parent_a["id"])

	resp = client.patch(f"/folders/{child['id']}", json={"parent_folder_id": parent_b["id"]})
	assert resp.status_code == 200
	assert resp.json()["parent_folder_id"] == parent_b["id"]


def test_reparent_to_root_via_explicit_null(client):
	register_and_login(client, "user@example.com")
	parent = _create_folder(client, "Parent")
	child = _create_folder(client, "Child", parent["id"])

	resp = client.patch(f"/folders/{child['id']}", json={"parent_folder_id": None})
	assert resp.status_code == 200
	assert resp.json()["parent_folder_id"] is None


def test_delete_empty_folder(client):
	register_and_login(client, "user@example.com")
	folder = _create_folder(client, "Disposable")
	resp = client.delete(f"/folders/{folder['id']}")
	assert resp.status_code == 204
	assert client.get(f"/folders/{folder['id']}").status_code == 404


def test_delete_nonempty_folder_is_blocked(client):
	register_and_login(client, "user@example.com")
	parent = _create_folder(client, "Parent")
	_create_folder(client, "Child", parent["id"])

	resp = client.delete(f"/folders/{parent['id']}")
	assert resp.status_code == 409
	# still there afterward
	assert client.get(f"/folders/{parent['id']}").status_code == 200


def test_prevent_self_parenting(client):
	register_and_login(client, "user@example.com")
	folder = _create_folder(client, "Loopy")
	resp = client.patch(f"/folders/{folder['id']}", json={"parent_folder_id": folder["id"]})
	assert resp.status_code == 400


def test_prevent_descendant_cycle_reparenting(client):
	register_and_login(client, "user@example.com")
	grandparent = _create_folder(client, "Grandparent")
	parent = _create_folder(client, "Parent", grandparent["id"])
	child = _create_folder(client, "Child", parent["id"])

	# try to move "Grandparent" under its own grandchild "Child"
	resp = client.patch(f"/folders/{grandparent['id']}", json={"parent_folder_id": child["id"]})
	assert resp.status_code == 400


# --- Cross-user isolation ----------------------------------------------------

def test_user_a_cannot_read_user_b_folder(client, second_client):
	register_and_login(client, "usera@example.com")
	register_and_login(second_client, "userb@example.com")

	b_folder = _create_folder(second_client, "B's Secret Folder")
	resp = client.get(f"/folders/{b_folder['id']}")
	assert resp.status_code == 404


def test_user_a_cannot_update_user_b_folder(client, second_client):
	register_and_login(client, "usera@example.com")
	register_and_login(second_client, "userb@example.com")

	b_folder = _create_folder(second_client, "B's Folder")
	resp = client.patch(f"/folders/{b_folder['id']}", json={"name": "Hijacked"})
	assert resp.status_code == 404


def test_user_a_cannot_delete_user_b_folder(client, second_client):
	register_and_login(client, "usera@example.com")
	register_and_login(second_client, "userb@example.com")

	b_folder = _create_folder(second_client, "B's Folder")
	resp = client.delete(f"/folders/{b_folder['id']}")
	assert resp.status_code == 404
	# still there for its real owner
	assert second_client.get(f"/folders/{b_folder['id']}").status_code == 200


def test_user_a_cannot_create_child_under_user_b_folder(client, second_client):
	register_and_login(client, "usera@example.com")
	register_and_login(second_client, "userb@example.com")

	b_folder = _create_folder(second_client, "B's Folder")
	resp = client.post("/folders", json={"name": "Intruder", "parent_folder_id": b_folder["id"]})
	assert resp.status_code == 404


def test_user_a_cannot_reparent_under_user_b_folder(client, second_client):
	register_and_login(client, "usera@example.com")
	register_and_login(second_client, "userb@example.com")

	a_folder = _create_folder(client, "A's Folder")
	b_folder = _create_folder(second_client, "B's Folder")

	resp = client.patch(f"/folders/{a_folder['id']}", json={"parent_folder_id": b_folder["id"]})
	assert resp.status_code == 404
