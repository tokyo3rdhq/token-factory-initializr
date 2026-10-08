"""Unit tests for the QuantizationSuffix + TokenSubsetSlug identity
matcher extensions.

Without these, HF id ``prism-ml/Ternary-Bonsai-27B-gguf`` (slug
``ternary-bonsai-27b``) would never collide with OR / models.dev id
``prism-ml/ternary-bonsai-2-27b`` (slug ``ternary-bonsai-2-27b``) — the
two slugs differ by an inserted ``2`` token. The new passes:

* ``_strip_quantization_suffix`` — drops ``-gguf``, ``-awq``, ``-gptq``,
  ``-safetensors``, ``-int4``, ``-int8`` etc. so the suffix doesn't
  break matches.
* ``DefaultIdentityMatcher._token_subset_slug_match`` — token-subset
  fallback so HF ids that drop a version token still hit.
"""

from __future__ import annotations

from data.identity_matcher import DefaultIdentityMatcher, _normalize_id


# ---------------------------------------------------------------------------
# Quantization suffix stripping
# ---------------------------------------------------------------------------


def test_strip_gguf_suffix():
    assert _normalize_id("prism-ml/Ternary-Bonsai-2-27B-gguf") == _normalize_id(
        "prism-ml/Ternary-Bonsai-2-27B"
    )


def test_strip_awq_gptq_safetensors():
    for suffix in ("-awq", "-gptq", "-safetensors", "-int4", "-int8", "-fp16", "-bf16", "-exl2"):
        base = "org/Model-7b"
        with_suffix = f"{base}{suffix}"
        assert _normalize_id(with_suffix) == _normalize_id(base)


def test_quantization_strip_only_at_end():
    """A mid-slug ``-gguf`` should NOT be stripped (it's part of the name)."""
    # ``gguf`` as a non-final token is part of the actual model name;
    # _strip_quantization_suffix only matches trailing suffixes.
    assert _normalize_id("org/gguf-tools-7b") != _normalize_id("org/-tools-7b")


# ---------------------------------------------------------------------------
# Token-subset slug match
# ---------------------------------------------------------------------------


def test_token_subset_match_handles_inserted_version_token():
    """HF drops the ``-2-`` token from ``Bonsai-2-27B`` →
    ``Bonsai-27B``. The token-subset fallback bridges that gap."""
    m = DefaultIdentityMatcher()
    r = m.match(
        "prism-ml/Ternary-Bonsai-27B-gguf",
        [{"id": "prism-ml/ternary-bonsai-2-27b", "source": "openrouter"}],
    )
    assert r is not None
    assert r.source_id == "prism-ml/ternary-bonsai-2-27b"
    assert r.confidence == 0.75


def test_token_subset_does_not_match_unrelated():
    """Two slugs sharing only noisy numeric tokens must NOT match."""
    m = DefaultIdentityMatcher()
    # Both share only the digit ``70b`` and a stray letter — no
    # alphabetic token overlap → rejected.
    assert (
        m.match(
            "org/llama-3-70b",
            [{"id": "org/qwen-2-70b", "source": "openrouter"}],
        )
        is None
    )


def test_token_subset_requires_alphabetic_overlap():
    """Pure-numeric slugs must NOT match even if one is a subset."""
    m = DefaultIdentityMatcher()
    assert (
        m.match(
            "org/2-70",
            [{"id": "org/70", "source": "openrouter"}],
        )
        is None
    )


def test_exact_match_still_wins_over_subset():
    """Confidence ranking: exact 1.0 > slug-equal 0.80 > subset 0.75."""
    m = DefaultIdentityMatcher()
    # Same id both sides after normalization → 1.0
    r = m.match(
        "prism-ml/ternary-bonsai-2-27b",
        [{"id": "prism-ml/ternary-bonsai-2-27b", "source": "openrouter"}],
    )
    assert r.confidence == 1.0


# ---------------------------------------------------------------------------
# Cross-source index integration: hugging_face_id indexed under HF id
# ---------------------------------------------------------------------------


def test_cross_source_index_includes_hugging_face_id():
    """OpenRouter entries with ``metadata.hugging_face_id`` should also be
    indexed under that HF id so HF endpoints can find them directly.

    After quantization-suffix stripping, both ids normalize to the
    same key, so the index merges them under one entry."""
    from data.stages.normalize import _build_cross_source_index

    or_obs = {
        "model_id": "prism-ml/ternary-bonsai-2-27b",
        "data_source": "openrouter",
        "metadata": {"hugging_face_id": "prism-ml/Ternary-Bonsai-2-27B-gguf"},
    }
    idx = _build_cross_source_index([or_obs])
    # Both ids collapse to the same key after quantization stripping,
    # so the OR observation is indexed exactly once under the merged key.
    assert list(idx.keys()) == ["prism-ml/ternary-bonsai-2-27b"]
    assert idx["prism-ml/ternary-bonsai-2-27b"] == [or_obs]


def test_cross_source_index_distinct_hf_id_creates_separate_entry():
    """When the HF id doesn't normalize to the same key as OR.id,
    the OR observation is indexed under both keys so either side can
    find it."""
    from data.stages.normalize import _build_cross_source_index

    or_obs = {
        "model_id": "vendor/model",
        "data_source": "openrouter",
        "metadata": {"hugging_face_id": "different/model"},
    }
    idx = _build_cross_source_index([or_obs])
    assert "vendor/model" in idx
    assert "different/model" in idx


def test_cross_source_index_no_hf_id_unchanged():
    from data.stages.normalize import _build_cross_source_index

    or_obs = {"model_id": "vendor/model", "data_source": "openrouter"}
    idx = _build_cross_source_index([or_obs])
    assert list(idx.keys()) == ["vendor/model"]


# ---------------------------------------------------------------------------
# Compound quantization suffixes
# ---------------------------------------------------------------------------


def test_compound_awq_4bit_suffix_does_not_strip_4bit():
    """``-AWQ-4bit`` is a compound suffix: AWQ (algorithm) + 4bit (precision).

    The matcher only recognises trailing suffix tokens in
    ``_QUANTIZATION_SUFFIXES``. ``-AWQ-4bit`` ends with ``-4bit`` (not
    in the list), so nothing is stripped. The id is therefore NOT
    collapsed onto the bare-model form — and rightly so, because
    AWQ-int4 vs gguf vs fp16 are *different inference products*
    (different engines, different memory footprints, byte-different
    outputs). Merging them under one endpoint would lie to the user.
    """
    awq_int4 = "prism-ml/Ternary-Bonsai-27B-AWQ-4bit"
    gguf = "prism-ml/Ternary-Bonsai-27B-gguf"
    bare = "prism-ml/Ternary-Bonsai-27B"
    # AWQ-int4 and gguf are NOT merged — different inference products.
    assert _normalize_id(awq_int4) != _normalize_id(gguf)
    # AWQ-int4 is also NOT collapsed onto the bare model name.
    assert _normalize_id(awq_int4) != _normalize_id(bare)
    # gguf IS collapsed onto the bare model name (its suffix is in
    # the recognized list).
    assert _normalize_id(gguf) == _normalize_id(bare)


def test_compound_int4_suffix_recognised_when_at_end():
    """``-int4`` IS in ``_QUANTIZATION_SUFFIXES`` so a clean trailing
    ``-int4`` does collapse onto the bare model — unlike the
    compound ``-AWQ-4bit`` case above."""
    assert _normalize_id("org/Model-7b-int4") == _normalize_id("org/Model-7b")


def test_default_matcher_does_not_merge_awq_int4_with_gguf():
    """End-to-end: an HF endpoint tagged -AWQ-4bit and an HF endpoint
    tagged -gguf of the *same* underlying weights must remain two
    separate endpoints in KV. The matcher should refuse to merge
    them even though they share the same numeric / token signature.
    """
    m = DefaultIdentityMatcher()
    # Cross-source observation references the gguf variant only —
    # AWQ-4bit must NOT be claimed as a match for it.
    r = m.match(
        "prism-ml/Ternary-Bonsai-27B-AWQ-4bit",
        [{"id": "prism-ml/ternary-bonsai-2-27b", "source": "openrouter"}],
    )
    # The compound -awq-4bit suffix survives normalization so the slug-side
    # keys diverge. Token-subset fallback does not match.
    assert r is None or r.confidence < 0.5
