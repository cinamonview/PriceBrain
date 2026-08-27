"""In-memory Firestore fake for unit tests — no Emulator required."""

from __future__ import annotations

import copy
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Iterator


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

    def get(self, transaction: "FakeTransaction | None" = None, **_kwargs: Any) -> FakeSnapshot:
        if transaction is not None:
            inner_txn = getattr(transaction, "_inner", transaction)
            if hasattr(inner_txn, "get_snapshot"):
                return inner_txn.get_snapshot(self._path)
            if hasattr(transaction, "get_snapshot"):
                return transaction.get_snapshot(self._path)
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


class FakeTransaction:
    """Buffered all-or-nothing writes with exclusive client lock (serializes workers)."""

    def __init__(self, client: "FakeFirestoreClient") -> None:
        self._client = client
        self._writes: list[tuple[str, dict[str, Any], bool]] = []

    def get_snapshot(self, path: str) -> FakeSnapshot:
        data = self._client._data.get(path)
        doc_id = path.rsplit("/", 1)[-1]
        return FakeSnapshot(doc_id, copy.deepcopy(data) if data is not None else None)

    def set(self, ref: Any, data: dict[str, Any], merge: bool = False) -> None:
        path = getattr(ref, "_path", None)
        if path is None:
            raise TypeError("transaction.set requires a document reference")
        self._writes.append((str(path), dict(data), merge))

    def commit(self) -> None:
        pending = copy.deepcopy(self._client._data)
        for path, data, merge in self._writes:
            if self._client.fail_write_if is not None and self._client.fail_write_if(path):
                raise RuntimeError(f"injected write failure: {path}")
            resolved = {key: _resolve_value(val) for key, val in data.items()}
            if merge and path in pending:
                merged = dict(pending[path])
                merged.update(resolved)
                pending[path] = merged
            else:
                pending[path] = resolved
        self._client._data = pending


class FakeFirestoreClient:
    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}
        self._txn_lock = threading.Lock()
        self.fail_write_if: Callable[[str], bool] | None = None
        # Fake-only retry simulation — not Firestore SDK retry instrumentation.
        self.simulate_transaction_retries = 0
        self.transaction_callback_runs = 0
        self.before_retry: Callable[[int], None] | None = None

    def collection(self, name: str) -> FakeCollectionReference:
        return FakeCollectionReference(self, name)

    def transaction(self) -> FakeTransaction:
        return FakeTransaction(self)

    def run_transaction(self, callback: Callable[[FakeTransaction], Any]) -> Any:
        with self._txn_lock:
            extra = int(self.simulate_transaction_retries)
            for attempt in range(extra):
                discarded = FakeTransaction(self)
                callback(discarded)
                self.transaction_callback_runs += 1
                if self.before_retry is not None:
                    self.before_retry(attempt)
            txn = FakeTransaction(self)
            result = callback(txn)
            self.transaction_callback_runs += 1
            txn.commit()
            return result

    def get_document(self, path: str) -> dict[str, Any] | None:
        return self._data.get(path)

    def paths(self) -> list[str]:
        return sorted(self._data.keys())
