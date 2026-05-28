from datetime import datetime, timezone

from kaizen.core.models import Message, Role
from kaizen.persona import (
    IDENTITY_PRIOR,
    ToneTag,
    classify_tone,
    render_prior,
    tone_hint,
)


def _user(text: str, hour: int = 14) -> Message:
    # Construct a user message at a specific hour so late-night bias is testable.
    msg = Message(role=Role.USER, content=text)
    object.__setattr__(
        msg, "created_at", datetime(2026, 5, 27, hour, 0, 0, tzinfo=timezone.utc)
    )
    return msg


def test_prior_is_non_empty_and_opinionated():
    assert "partner" in IDENTITY_PRIOR
    assert "assistant" in IDENTITY_PRIOR  # "not a helpful assistant"
    assert "not a helpful assistant" in IDENTITY_PRIOR


def test_render_prior_no_traits_returns_floor():
    assert render_prior() == IDENTITY_PRIOR
    assert render_prior([]) == IDENTITY_PRIOR
    # Blank / whitespace traits are filtered out.
    assert render_prior(["  ", ""]) == IDENTITY_PRIOR


def test_render_prior_with_learned_traits_appends_block():
    rendered = render_prior(["Never open replies with 'sorry'.", "Prefer ruff over black."])
    assert rendered.startswith(IDENTITY_PRIOR)
    assert "Learned voice:" in rendered
    assert "- Never open replies with 'sorry'." in rendered
    assert "- Prefer ruff over black." in rendered


def test_classify_empty_returns_neutral():
    assert classify_tone([]) is ToneTag.NEUTRAL
    # Only assistant messages → no user signal.
    assert classify_tone([Message(role=Role.ASSISTANT, content="hi")]) is ToneTag.NEUTRAL


def test_classify_terse():
    assert classify_tone([_user("yep")]) is ToneTag.TERSE
    assert classify_tone([_user("k")]) is ToneTag.TERSE


def test_classify_playful():
    assert classify_tone([_user("lmao that's wild!!")]) is ToneTag.PLAYFUL


def test_classify_pissed_beats_sarcastic_when_both_fire():
    # Caps + profanity → pissed; "/s" would normally be sarcastic.
    tag = classify_tone([_user("WHAT THE FUCK is this /s")])
    assert tag is ToneTag.PISSED


def test_classify_sarcastic():
    assert classify_tone([_user("oh sure thing, that'll work")]) is ToneTag.SARCASTIC


def test_classify_tired():
    assert classify_tone([_user("ugh idk man...")]) is ToneTag.TIRED


def test_classify_tired_late_night_bias():
    # A short lowercase fragment at 03:00 UTC should land as tired,
    # not just terse, thanks to the hour bump.
    tag = classify_tone([_user("fine whatever", hour=3)])
    assert tag is ToneTag.TIRED


def test_classify_curious():
    assert classify_tone([_user("why does the router prefer LOCAL?")]) is ToneTag.CURIOUS


def test_classify_uses_last_window_only():
    # Old messages should not dominate; window=2 keeps only the last two users.
    messages = [
        _user("ugh whatever..."),  # would be tired
        _user("ugh whatever..."),
        _user("why is this happening?"),  # curious
        _user("why else would I ask?"),  # curious
    ]
    assert classify_tone(messages, window=2) is ToneTag.CURIOUS


def test_tone_hint_neutral_is_empty():
    assert tone_hint(ToneTag.NEUTRAL) == ""


def test_tone_hint_pissed_is_blunt():
    hint = tone_hint(ToneTag.PISSED)
    assert hint
    assert "apolog" in hint.lower()  # explicit guidance not to over-apologise


def test_tone_hint_tired_says_be_brief():
    hint = tone_hint(ToneTag.TIRED)
    assert "brief" in hint.lower()


def test_every_tag_except_neutral_has_a_hint():
    for tag in ToneTag:
        if tag is ToneTag.NEUTRAL:
            continue
        assert tone_hint(tag), f"missing hint for {tag}"
