from kaizen.core.models import Message, Role, Session
from kaizen.memory.inmemory import InMemoryStore
from kaizen.memory.scribe import Scribe, parse_facts
from kaizen.providers.base import CompletionRequest, CompletionResponse, Tier


def test_parse_facts_basic():
    facts = parse_facts(
        'Sure: [{"subject":"user","attribute":"building","value":"a trading platform called Hermes"}]'
    )
    assert len(facts) == 1
    assert facts[0].value == "a trading platform called Hermes"
    assert facts[0].subject == "user"
    assert facts[0].source == "scribe"


def test_parse_facts_no_json():
    assert parse_facts("nothing structured here") == []


def test_parse_facts_skips_valueless_entries():
    assert parse_facts('[{"subject":"user","attribute":"likes"}]') == []


def test_parse_facts_multiple():
    facts = parse_facts('[{"value":"rust"},{"value":"quant finance"}]')
    assert [f.value for f in facts] == ["rust", "quant finance"]


class _CountingProvider:
    """Emits one unique fact per call, so dedup/eviction is observable."""

    name = "counting-stub"
    tier = Tier.LOCAL

    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        self.calls += 1
        return CompletionResponse(
            text=f'[{{"subject":"user","attribute":"n","value":"fact-{self.calls}"}}]',
            model="counting-stub",
        )


async def test_seen_cache_is_bounded():
    scribe = Scribe(_CountingProvider(), InMemoryStore(), max_seen=3)
    session = Session()
    for i in range(6):
        session.add(Message(role=Role.USER, content=f"turn {i}"))
        await scribe.observe(session)
    assert len(scribe._seen) <= 3


async def test_watermarks_are_bounded_by_session_count():
    scribe = Scribe(_CountingProvider(), InMemoryStore(), max_sessions=2)
    for i in range(5):
        session = Session()
        session.add(Message(role=Role.USER, content=f"session {i}"))
        await scribe.observe(session)
    assert len(scribe._watermark) <= 2


async def test_dedup_still_works_within_bounds():
    provider = _CountingProvider()
    memory = InMemoryStore()
    scribe = Scribe(provider, memory, max_seen=100)

    class _RepeatProvider:
        name = "repeat"
        tier = Tier.LOCAL

        async def complete(self, request: CompletionRequest) -> CompletionResponse:
            return CompletionResponse(
                text='[{"subject":"user","attribute":"n","value":"same-fact"}]',
                model="repeat",
            )

    scribe.provider = _RepeatProvider()
    session = Session()
    for i in range(3):
        session.add(Message(role=Role.USER, content=f"turn {i}"))
        await scribe.observe(session)
    facts = await memory.search("same-fact", k=10)
    assert len([f for f in facts if f.value == "same-fact"]) == 1
