from kaizen.memory.scribe import parse_facts


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
