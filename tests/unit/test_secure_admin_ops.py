"""Secure admin storage tests."""

from __future__ import annotations

from pathlib import Path

from patch_machine.archive.access_control import AccessControlStore, UserRecord
from patch_machine.archive.secret_store import ApiKeyRecord, SecretStore
from patch_machine.archive.uploads import UploadStore


def test_secret_store_masks_and_round_trips(archive_tmp: Path) -> None:
    store = SecretStore(archive_tmp, master_key="test-master-key")

    store.upsert(ApiKeyRecord(provider="openai", api_key="sk-test-1234567890", model="gpt-x"))

    listed = store.list_masked()
    openai = next(item for item in listed if item["provider"] == "openai")
    assert openai["configured"] is True
    assert openai["masked_value"] == "sk-t...7890"
    assert store.read("openai").api_key == "sk-test-1234567890"  # type: ignore[union-attr]


def test_access_control_blocks_viewer_from_admin_permissions(archive_tmp: Path) -> None:
    store = AccessControlStore(archive_tmp)
    store.upsert_user(UserRecord(id="viewer1", display_name="Viewer", title="사원", role_id="viewer"))

    assert store.has_permission("owner", "admin:api_keys") is True
    assert store.has_permission("viewer1", "admin:api_keys") is False
    assert store.has_permission("viewer1", "work:read") is True


def test_upload_store_saves_and_deletes_file(archive_tmp: Path) -> None:
    store = UploadStore(archive_tmp)
    source = __import__("io").BytesIO(b"hello")

    record = store.save(filename="hello.txt", source=source, description="demo")

    assert (archive_tmp / record.path).exists()
    assert store.list()[0]["filename"] == "hello.txt"
    assert store.delete(record.id) is True
    assert not (archive_tmp / record.path).exists()
