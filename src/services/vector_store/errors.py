"""Typed exceptions for vector store runtime failures."""

from __future__ import annotations

from typing import List


class VectorStoreError(Exception):
    """Base exception for vector store operations."""


class IndexNotReadyError(VectorStoreError):
    """Raised when index operations are attempted before index setup."""

    def __init__(self, index_name: str, reason: str):
        self.index_name = index_name
        self.reason = reason
        super().__init__(f"Index '{index_name}' is not ready: {reason}")


class IncompatibleIndexSchemaError(VectorStoreError):
    """Raised when existing index schema does not match required hybrid schema."""

    def __init__(self, index_name: str, issues: List[str]):
        self.index_name = index_name
        self.issues = issues
        issue_text = "; ".join(issues)
        super().__init__(f"Incompatible schema for index '{index_name}': {issue_text}")
