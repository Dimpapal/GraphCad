"""Whole-document transactions: one gesture or form apply is one undo step."""
from __future__ import annotations
from copy import deepcopy
from .model import Document


class History:
    def __init__(self, document: Document, limit: int = 150):
        self.limit = limit
        self.reset(document)

    def reset(self, document: Document) -> None:
        self.document = document
        self._undo: list[tuple[dict, dict, str]] = []
        self._redo: list[tuple[dict, dict, str]] = []
        self._saved = document.to_dict()

    def commit(self, before_dict: dict, label: str = "Edit") -> bool:
        after = self.document.to_dict()
        if before_dict == after:
            return False
        self._undo.append((deepcopy(before_dict), after, label))
        self._undo = self._undo[-self.limit:]
        self._redo.clear()
        return True

    def undo(self) -> Document | None:
        if not self._undo:
            return None
        transaction = self._undo.pop()
        self._redo.append(transaction)
        self.document = Document.from_dict(transaction[0])
        return self.document

    def redo(self) -> Document | None:
        if not self._redo:
            return None
        transaction = self._redo.pop()
        self._undo.append(transaction)
        self.document = Document.from_dict(transaction[1])
        return self.document

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @property
    def undo_label(self) -> str:
        return self._undo[-1][2] if self._undo else ""

    @property
    def redo_label(self) -> str:
        return self._redo[-1][2] if self._redo else ""

    def mark_saved(self, document: Document | None = None) -> None:
        self._saved = (document or self.document).to_dict()

    def is_dirty(self, document: Document | None = None) -> bool:
        return (document or self.document).to_dict() != self._saved
