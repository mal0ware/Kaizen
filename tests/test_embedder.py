"""Offline tests for the deterministic HashEmbedder (no infra required)."""
import math

from kaizen.memory.embedder import HashEmbedder


async def test_dimension_and_determinism():
    embedder = HashEmbedder(dim=64)
    a = await embedder.embed("kaizen builds a black hole renderer")
    b = await embedder.embed("kaizen builds a black hole renderer")
    assert len(a) == 64
    assert a == b  # identical text -> identical vector


async def test_unit_normalized():
    vec = await HashEmbedder(dim=128).embed("some tokens here for normalization")
    assert math.isclose(math.sqrt(sum(x * x for x in vec)), 1.0, rel_tol=1e-9)


async def test_empty_text_is_defined_unit_vector():
    vec = await HashEmbedder(dim=32).embed("!!! --- ???")  # no word tokens
    assert math.isclose(math.sqrt(sum(x * x for x in vec)), 1.0, rel_tol=1e-9)


async def test_shared_tokens_are_closer_than_disjoint():
    embedder = HashEmbedder(dim=256)

    def cosine(u: list[float], v: list[float]) -> float:
        return sum(a * b for a, b in zip(u, v))  # both unit-normalized

    base = await embedder.embed("black hole renderer in metal and vulkan")
    near = await embedder.embed("black hole renderer using vulkan")
    far = await embedder.embed("hiking alpine trails on the weekend")

    assert cosine(base, near) > cosine(base, far)


def test_rejects_nonpositive_dim():
    import pytest

    with pytest.raises(ValueError):
        HashEmbedder(dim=0)
