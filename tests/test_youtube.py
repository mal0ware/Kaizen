from kaizen.tools.youtube import classify_error, extract_video_id


def test_extract_from_watch_url():
    assert extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_extract_from_short_url():
    assert extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_extract_bare_id():
    assert extract_video_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_extract_none_for_non_youtube():
    assert extract_video_id("just some text") is None


def test_classify_transient_block():
    class IpBlocked(Exception): ...

    assert classify_error(IpBlocked()) == "transient"


def test_classify_no_captions():
    class TranscriptsDisabled(Exception): ...

    assert classify_error(TranscriptsDisabled()) == "no_captions"


def test_classify_unknown_is_not_swallowed():
    # the ytmerge bug: an unknown error must NOT be treated as "no captions"
    assert classify_error(ValueError("boom")) == "unknown"
