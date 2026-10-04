"""Unit tests for the version-separator normalization added to
``data.identity_matcher._normalize_id``.

OpenRouter spells minor versions with a dot (``glm-5.3``) while NVIDIA
spells them with a dash (``glm-5-3``). Without unifying the two forms,
identical releases never collide.
"""

from __future__ import annotations

from data.identity_matcher import DefaultIdentityMatcher, _normalize_id


# ---------------------------------------------------------------------------
# Direct normalization
# ---------------------------------------------------------------------------


def test_dot_version_becomes_dash():
    assert _normalize_id("z-ai/glm-5.3-flash") == "z-ai/glm-5-3-flash"


def test_underscore_version_becomes_dash():
    assert _normalize_id("vendor/model-3_2") == "vendor/model-3-2"


def test_already_dashed_version_unchanged():
    assert _normalize_id("z-ai/glm-5-3-flash") == "z-ai/glm-5-3-flash"


def test_case_insensitive():
    assert _normalize_id("GLM-5.3-Flash") == _normalize_id("glm-5-3-flash")


def test_non_version_dash_preserved():
    """Dashes between words (slug boundaries) must NOT be touched."""
    assert _normalize_id("qwen3-vl-plus") == "qwen3-vl-plus"


def test_multiple_versions_in_same_id():
    """All digit<sep>digit sequences collapse, regardless of slug position."""
    assert _normalize_id("vendor/foo-3.2-bar-4") == "vendor/foo-3-2-bar-4"
    # The trailing ``.4`` after a non-digit ``bar`` doesn't match the
    # ``digit<sep>digit`` pattern, so it stays as a literal ``.4``
    # (rare in practice — version numbers almost always appear as
    # digit.digit or digit-digit).
    assert _normalize_id("vendor/foo-3.2-bar.4") != _normalize_id("vendor/foo-3-2-bar-4")


def test_combined_with_date_strip():
    """Date suffix stripping must still work after version unification."""
    # OR sometimes appends a date like ``-20251022``.
    before = _normalize_id("vendor/foo-5.3-20251022")
    after = _normalize_id("vendor/foo-5-3")
    assert before == after


def test_combined_with_owner_alias():
    """Owner alias must still apply after version unification."""
    # deepseek-v4.1-flash normalizes to deepseek-v4-1-flash, and the
    # owner alias then collapses deepseek-ai/... to deepseek/.
    assert _normalize_id("deepseek-ai/deepseek-v4.1-flash") == _normalize_id(
        "deepseek/deepseek-v4-1-flash"
    )


# ---------------------------------------------------------------------------
# Match behavior
# ---------------------------------------------------------------------------


def test_nvidia_dash_version_matches_or_dot_version_exact():
    """NVIDIA's ``z-ai/glm-5-3-flash`` matches OR's ``z-ai/glm-5.3-flash``
    with confidence 1.0 after version-unifying normalization.
    """
    m = DefaultIdentityMatcher()
    r = m.match(
        "z-ai/glm-5-3-flash",
        [{"id": "z-ai/glm-5.3-flash", "source": "openrouter"}],
    )
    assert r is not None
    assert r.source_id == "z-ai/glm-5.3-flash"
    assert r.confidence == 1.0


def test_nvidia_dash_version_matches_or_dot_version_bare_slug():
    """Slug fallback still works once the slugs match after normalization."""
    m = DefaultIdentityMatcher()
    r = m.match(
        "z-ai/glm-5-3-flash",
        [{"id": "glm-5.3-flash", "source": "openrouter"}],
    )
    assert r is not None
    assert r.confidence == 0.8  # slug-fallback, not exact


def test_different_minor_versions_do_not_match():
    """``5.3`` and ``5.4`` are different releases — must not collide."""
    m = DefaultIdentityMatcher()
    r = m.match(
        "vendor/model-5-3",
        [{"id": "vendor/model-5.4", "source": "openrouter"}],
    )
    assert r is None


def test_owner_alias_still_works_after_version_normalization():
    """deepseek-v4.1-flash normalizes to a form that the owner alias
    can collapse identically to the OR-side id."""
    m = DefaultIdentityMatcher()
    r = m.match(
        "deepseek-ai/deepseek-v4.1-flash",
        [{"id": "deepseek/deepseek-v4.1-flash", "source": "openrouter"}],
    )
    assert r is not None
    assert r.confidence == 1.0
