from kaizen.identity.models import Account, Belief, Entity
from kaizen.identity.store import IdentityGraph


def test_multiple_accounts_resolve_to_one_entity():
    g = IdentityGraph()
    mal = g.add_entity(Entity(display_name="Mal"))
    a1 = g.add_account(Account(platform="discord", handle="Stroker Ace", platform_id="111"))
    a2 = g.add_account(Account(platform="discord", handle="not_mal", platform_id="222"))
    g.link(a1, mal)
    g.link(a2, mal)
    assert g.resolve("discord", "111") is mal
    assert g.resolve("discord", "222") is mal


def test_reputation_is_separate_from_entity_facts():
    g = IdentityGraph()
    subject = g.add_entity(Entity(display_name="Riley", facts={"field": "pre-med"}))
    observer = g.add_entity(Entity(display_name="Mal"))
    g.record_belief(
        Belief(observer.id, subject.id, "thinks AI won't replace surgeons", confidence=0.8)
    )
    reps = g.reputation(subject.id)
    # the belief lives on the edge, not on the subject's objective facts
    assert reps and "surgeons" in reps[0].statement
    assert "field" in subject.facts and "surgeons" not in str(subject.facts)
