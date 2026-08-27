"""Firestore read/write instrumentation — cost measurement and write guards.

Wraps any Firestore-like client (the in-memory fake or a real/emulator client) and
counts document reads and writes. With block_writes=True any write attempt raises,
which is how "dry-run performs zero writes" is proven rather than assumed.
"""

from __future__ import annotations

from typing import Any, Iterator


class FirestoreWriteBlocked(AssertionError):
    """A write was attempted while writes were blocked."""


class _Counters:
    def __init__(self, *, block_writes: bool) -> None:
        self.reads = 0
        self.writes = 0
        self.block_writes = block_writes
        self.write_paths: list[str] = []
        self.read_paths: list[str] = []

    def record_read(self, path: str) -> None:
        self.reads += 1
        self.read_paths.append(path)

    def record_write(self, path: str) -> None:
        if self.block_writes:
            raise FirestoreWriteBlocked(f"write blocked: {path}")
        self.writes += 1
        self.write_paths.append(path)


class _CountingDocument:
    def __init__(self, inner: Any, counters: _Counters, path: str) -> None:
        self._inner = inner
        self._counters = counters
        self._path = path

    @property
    def id(self) -> str:
        return self._inner.id

    def collection(self, name: str) -> "_CountingCollection":
        return _CountingCollection(
            self._inner.collection(name), self._counters, f"{self._path}/{name}"
        )

    def get(self, transaction: Any | None = None, **kwargs: Any) -> Any:
        self._counters.record_read(self._path)
        inner_txn = getattr(transaction, "_inner", transaction) if transaction is not None else None
        return self._inner.get(transaction=inner_txn, **kwargs)

    def set(self, data: dict[str, Any], merge: bool = False) -> Any:
        self._counters.record_write(self._path)
        return self._inner.set(data, merge=merge)

    def update(self, data: dict[str, Any]) -> Any:
        self._counters.record_write(self._path)
        return self._inner.update(data)

    def delete(self) -> Any:
        self._counters.record_write(self._path)
        return self._inner.delete()


class _CountingQuery:
    def __init__(self, inner: Any, counters: _Counters, path: str) -> None:
        self._inner = inner
        self._counters = counters
        self._path = path

    def limit(self, count: int) -> "_CountingQuery":
        return _CountingQuery(self._inner.limit(count), self._counters, self._path)

    def order_by(self, *args: Any, **kwargs: Any) -> "_CountingQuery":
        return _CountingQuery(
            self._inner.order_by(*args, **kwargs), self._counters, self._path
        )

    def where(self, *args: Any, **kwargs: Any) -> "_CountingQuery":
        return _CountingQuery(
            self._inner.where(*args, **kwargs), self._counters, self._path
        )

    def stream(self) -> Iterator[Any]:
        for snapshot in self._inner.stream():
            self._counters.record_read(f"{self._path}/{snapshot.id}")
            yield snapshot


class _CountingCollection(_CountingQuery):
    def document(self, doc_id: str | None = None) -> _CountingDocument:
        inner = self._inner.document(doc_id)
        return _CountingDocument(inner, self._counters, f"{self._path}/{inner.id}")


class CountingFirestoreClient:
    """Read/write-counting proxy around a Firestore-like client."""

    def __init__(self, inner: Any, *, block_writes: bool = False) -> None:
        self._inner = inner
        self._counters = _Counters(block_writes=block_writes)

    @property
    def reads(self) -> int:
        return self._counters.reads

    @property
    def writes(self) -> int:
        return self._counters.writes

    @property
    def write_paths(self) -> list[str]:
        return list(self._counters.write_paths)

    @property
    def read_paths(self) -> list[str]:
        return list(self._counters.read_paths)

    def reset(self) -> None:
        self._counters.reads = 0
        self._counters.writes = 0
        self._counters.write_paths.clear()
        self._counters.read_paths.clear()

    def collection(self, name: str) -> _CountingCollection:
        return _CountingCollection(self._inner.collection(name), self._counters, name)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)
