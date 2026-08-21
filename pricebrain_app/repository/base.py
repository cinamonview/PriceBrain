"""Base repository — Admin SDK access only (docs/09, docs/13)."""

from __future__ import annotations

from google.cloud.firestore_v1 import Client as FirestoreClient


class BaseRepository:
    def __init__(self, db: FirestoreClient) -> None:
        self._db = db

    @property
    def db(self) -> FirestoreClient:
        return self._db
