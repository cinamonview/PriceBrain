"""In-memory Firestore fake for unit tests — no Emulator required."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Iterator


class _ServerTimestamp:
    pass


SERVER_TIMESTAMP = _ServerTimestamp()


def _resolve_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {key: _resolve_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_value(item) for item in value]
    if value is SERVER_TIMESTAMP:
        return datetime.now(timezone.utc)
    # google.cloud.firestore_v1.transforms.SERVER_TIMESTAMP sentinel
    return datetime.now(timezone.utc)


class FakeSnapshot:
    def __init__(self, doc_id: str, data: dict[str, Any] | None) -> None:
        self.id = doc_id
        self._data = data

    @property
    def exists(self) -> bool:
        return self._data is not None

    def to_dict(self) -> dict[str, Any] | None:
        return dict(self._data) if self._data is not None else None


class FakeQuery:
    def __init__(self, client: "FakeFirestoreClient", collection_path: str, limit: int) -> None:
        self._client = client
        self._collection_path = collection_path
        self._limit = limit

    def stream(self) -> Iterator[FakeSnapshot]:
        prefix = f"{self._collection_path}/"
        count = 0
        for path, data in sorted(self._client._data.items()):
            if not path.startswith(prefix):
                continue
            remainder = path[len(prefix) :]
            if "/" in remainder:
                continue
            yield FakeSnapshot(remainder.split("/")[-1], data)
            count += 1
            if count >= self._limit:
                break


class FakeCollectionReference:
    def __init__(self, client: "FakeFirestoreClient", collection_path: str) -> None:
        self._client = client
        self._collection_path = collection_path

    def document(self, doc_id: str | None = None) -> "FakeDocumentReference":
        if doc_id is None:
            doc_id = uuid.uuid4().hex
        return FakeDocumentReference(self._client, f"{self._collection_path}/{doc_id}")

    def stream(self) -> Iterator[FakeSnapshot]:
        prefix = f"{self._collection_path}/"
        for path, data in sorted(self._client._data.items()):
            if not path.startswith(prefix):
                continue
            remainder = path[len(prefix) :]
            if "/" in remainder:
                continue
            yield FakeSnapshot(remainder, data)

    def limit(self, count: int) -> FakeQuery:
        return FakeQuery(self._client, self._collection_path, count)


class FakeDocumentReference:
    def __init__(self, client: "FakeFirestoreClient", path: str) -> None:
        self._client = client
        self._path = path

    @property
    def id(self) -> str:
        return self._path.rsplit("/", 1)[-1]

    def collection(self, name: str) -> FakeCollectionReference:
        return FakeCollectionReference(self._client, f"{self._path}/{name}")

    def get(self) -> FakeSnapshot:
        data = self._client._data.get(self._path)
        doc_id = self._path.rsplit("/", 1)[-1]
        return FakeSnapshot(doc_id, data)

    def set(self, data: dict[str, Any], merge: bool = False) -> None:
        resolved = {key: _resolve_value(val) for key, val in data.items()}
        if merge and self._path in self._client._data:
            merged = dict(self._client._data[self._path])
            merged.update(resolved)
            self._client._data[self._path] = merged
        else:
            self._client._data[self._path] = resolved

    def update(self, data: dict[str, Any]) -> None:
        if self._path not in self._client._data:
            self._client._data[self._path] = {}
        self._client._data[self._path].update(
            {key: _resolve_value(val) for key, val in data.items()}
        )


class FakeFirestoreClient:
    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    def collection(self, name: str) -> FakeCollectionReference:
        return FakeCollectionReference(self, name)

    def get_document(self, path: str) -> dict[str, Any] | None:
        return self._data.get(path)

    def paths(self) -> list[str]:
        return sorted(self._data.keys())
