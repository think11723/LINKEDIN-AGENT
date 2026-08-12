"""Storage module for approval system."""

from approval.storage.interface import StorageInterface
from approval.storage.json_storage import JSONStorage

__all__ = ["StorageInterface", "JSONStorage"]
