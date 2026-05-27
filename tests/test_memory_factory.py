from kaizen.config import Settings
from kaizen.memory.factory import build_memory
from kaizen.memory.inmemory import InMemoryStore


def test_falls_back_to_in_memory_without_database_url():
    fallback = InMemoryStore()
    assert build_memory(Settings(database_url=None), fallback) is fallback
