import threading
from typing import Optional


class IdAllocator:
    def __init__(self, start_at: int = 1):
        self._next_id = start_at
        self._lock = threading.Lock()

    @property
    def next_value(self) -> int:
        return self._next_id

    def allocate(self) -> int:
        with self._lock:
            current = self._next_id
            self._next_id += 1
            return current

    def seed_from_existing(self, max_existing: Optional[int]) -> None:
        base_value = int(max_existing or 0)
        with self._lock:
            self._next_id = max(self._next_id, base_value + 1)
