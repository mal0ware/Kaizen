from kaizen.memory.base import Fact
from kaizen.memory.inmemory import InMemoryStore


async def test_add_and_search():
    store = InMemoryStore()
    await store.add_fact(Fact(subject="mal", attribute="prefers", value="dark mode terminals"))
    await store.add_fact(Fact(subject="mal", attribute="builds", value="quant trading platform"))

    results = await store.search("terminal", k=5)
    assert results and results[0].value == "dark mode terminals"


async def test_search_no_match_returns_empty():
    store = InMemoryStore()
    await store.add_fact(Fact(subject="mal", attribute="likes", value="rust"))
    assert await store.search("xylophone") == []
