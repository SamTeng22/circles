"""Tests for the conflict detection service.

These pin the two-pass contract: pgvector supplies candidate pairs from *other*
users, Gemini decides which of those are genuine contradictions, and only those
get persisted. The pool and the model are faked so no DB or network is needed.
"""
import pytest

from app.services import conflict_detector as cd


class FakeResponse:
    def __init__(self, text):
        self.text = text


def _chunk(chunk_id, user_id, content, embedding="[0.1,0.2]"):
    """A row as returned by the new-note chunk query."""
    return {
        "id": chunk_id,
        "user_id": user_id,
        "content": content,
        "embedding": embedding,
    }


def _neighbor(chunk_id, note_id, user_id, content, distance):
    """A row as returned by the ANN neighbour query.

    `distance` is L2; the service converts it to cosine distance as l2^2 / 2.
    """
    return {
        "id": chunk_id,
        "note_id": note_id,
        "user_id": user_id,
        "content": content,
        "distance": distance,
    }


# L2 distances either side of SIMILARITY_THRESHOLD (0.25 cosine).
NEAR = 0.5   # cosine 0.125 -> passes
FAR = 1.0    # cosine 0.5   -> filtered out


def _patch_pool(monkeypatch, fake_pool):
    async def _get_pool():
        return fake_pool
    monkeypatch.setattr(cd, "get_pool", _get_pool)


def _patch_model(monkeypatch, replies):
    """Fake model.generate_content, returning `replies` in order.

    Records each prompt so tests can assert both chunk texts were sent.
    """
    prompts = []
    queue = list(replies)

    class FakeModel:
        def generate_content(self, prompt):
            prompts.append(prompt)
            return FakeResponse(queue.pop(0) if queue else "{}")

    monkeypatch.setattr(cd, "model", FakeModel())
    return prompts


CONTRADICTION = (
    '{"classification": "contradiction", '
    '"explanation": "One says the battle was in 1815, the other 1812."}'
)
AGREEMENT = '{"classification": "agreement", "explanation": ""}'


async def test_persists_contradiction_with_both_notes_and_users(
    monkeypatch, fake_conn, fake_pool
):
    _patch_pool(monkeypatch, fake_pool)
    fake_conn.queue_fetch(
        [_chunk("chunk-a", "user-1", "The battle was in 1815.")],
        [_neighbor("chunk-b", "note-old", "user-2", "The battle was in 1812.", NEAR)],
    )
    _patch_model(monkeypatch, [CONTRADICTION])

    count = await cd.detect_conflicts_for_note("note-new", "circle-1")

    assert count == 1
    inserts = fake_conn.statements_matching("INSERT INTO conflicts")
    assert len(inserts) == 1
    _, args = inserts[0]
    assert args == (
        "circle-1",
        "chunk-a", "chunk-b",
        "note-new", "note-old",
        "user-1", "user-2",
        "One says the battle was in 1815, the other 1812.",
    )


async def test_agreement_is_not_persisted(monkeypatch, fake_conn, fake_pool):
    # High similarity usually means agreement — the whole reason for pass two.
    _patch_pool(monkeypatch, fake_pool)
    fake_conn.queue_fetch(
        [_chunk("chunk-a", "user-1", "Mitochondria produce ATP.")],
        [_neighbor("chunk-b", "note-old", "user-2", "ATP comes from mitochondria.", NEAR)],
    )
    _patch_model(monkeypatch, [AGREEMENT])

    assert await cd.detect_conflicts_for_note("note-new", "circle-1") == 0
    assert not fake_conn.ran("INSERT INTO conflicts")


async def test_dissimilar_pairs_never_reach_the_model(
    monkeypatch, fake_conn, fake_pool
):
    # Pairs above the distance threshold must be dropped before paying for an
    # LLM call.
    _patch_pool(monkeypatch, fake_pool)
    fake_conn.queue_fetch(
        [_chunk("chunk-a", "user-1", "text a")],
        [_neighbor("chunk-b", "note-old", "user-2", "text b", FAR)],
    )
    prompts = _patch_model(monkeypatch, [CONTRADICTION])

    assert await cd.detect_conflicts_for_note("note-new", "circle-1") == 0
    assert prompts == []
    assert not fake_conn.ran("INSERT INTO conflicts")


async def test_query_excludes_same_note_and_same_user(
    monkeypatch, fake_conn, fake_pool
):
    # Self-comparison and same-author pairs are excluded in SQL, so the fake
    # never sees them; assert the filters are actually in the statement.
    _patch_pool(monkeypatch, fake_pool)
    fake_conn.queue_fetch([_chunk("chunk-a", "user-1", "text a")], [])
    _patch_model(monkeypatch, [])

    await cd.detect_conflicts_for_note("note-new", "circle-1")

    sql, args = fake_conn.statements_matching("ORDER BY embedding <->")[0]
    assert "note_id != $3" in sql
    assert "user_id != $4" in sql
    assert args == ("circle-1", "[0.1,0.2]", "note-new", "user-1", cd.NEIGHBORS_PER_CHUNK)


async def test_no_chunks_short_circuits(monkeypatch, fake_conn, fake_pool):
    # A note with no embeddable chunks must not run any neighbour search.
    _patch_pool(monkeypatch, fake_pool)
    fake_conn.queue_fetch([])
    _patch_model(monkeypatch, [])

    assert await cd.detect_conflicts_for_note("note-new", "circle-1") == 0
    assert not fake_conn.ran("ORDER BY embedding <->")


async def test_both_chunk_texts_are_sent_to_the_model(
    monkeypatch, fake_conn, fake_pool
):
    _patch_pool(monkeypatch, fake_pool)
    fake_conn.queue_fetch(
        [_chunk("chunk-a", "user-1", "AAA_UNIQUE")],
        [_neighbor("chunk-b", "note-old", "user-2", "BBB_UNIQUE", NEAR)],
    )
    prompts = _patch_model(monkeypatch, [AGREEMENT])

    await cd.detect_conflicts_for_note("note-new", "circle-1")

    assert len(prompts) == 1
    assert "AAA_UNIQUE" in prompts[0]
    assert "BBB_UNIQUE" in prompts[0]


async def test_pair_count_is_capped(monkeypatch, fake_conn, fake_pool):
    # A big upload into a big circle must not fan out into unbounded LLM calls.
    monkeypatch.setattr(cd, "MAX_PAIRS_PER_NOTE", 2)
    _patch_pool(monkeypatch, fake_pool)
    fake_conn.queue_fetch(
        [_chunk("chunk-a", "user-1", "text a")],
        [
            _neighbor(f"chunk-{i}", "note-old", "user-2", f"text {i}", NEAR)
            for i in range(5)
        ],
    )
    prompts = _patch_model(monkeypatch, [AGREEMENT] * 5)

    await cd.detect_conflicts_for_note("note-new", "circle-1")

    assert len(prompts) == 2


async def test_closest_pairs_are_kept_when_capped(monkeypatch, fake_conn, fake_pool):
    # When the cap bites, spend the budget on the most similar pairs.
    monkeypatch.setattr(cd, "MAX_PAIRS_PER_NOTE", 1)
    _patch_pool(monkeypatch, fake_pool)
    fake_conn.queue_fetch(
        [_chunk("chunk-a", "user-1", "text a")],
        [
            _neighbor("chunk-far", "note-old", "user-2", "FAR_TEXT", 0.7),
            _neighbor("chunk-near", "note-old", "user-2", "NEAR_TEXT", 0.1),
        ],
    )
    prompts = _patch_model(monkeypatch, [AGREEMENT])

    await cd.detect_conflicts_for_note("note-new", "circle-1")

    assert "NEAR_TEXT" in prompts[0]
    assert "FAR_TEXT" not in prompts[0]


async def test_model_failure_skips_pair_without_raising(
    monkeypatch, fake_conn, fake_pool
):
    # One bad reply must not abort detection for the rest of the note.
    _patch_pool(monkeypatch, fake_pool)
    fake_conn.queue_fetch(
        [_chunk("chunk-a", "user-1", "text a")],
        [
            _neighbor("chunk-b", "note-old", "user-2", "text b", 0.1),
            _neighbor("chunk-c", "note-old", "user-2", "text c", 0.2),
        ],
    )
    _patch_model(monkeypatch, ["not json at all", CONTRADICTION])

    count = await cd.detect_conflicts_for_note("note-new", "circle-1")

    assert count == 1
    inserts = fake_conn.statements_matching("INSERT INTO conflicts")
    assert inserts[0][1][2] == "chunk-c"


async def test_contradiction_without_explanation_gets_a_fallback(
    monkeypatch, fake_conn, fake_pool
):
    # explanation is NOT NULL in the schema, so an empty one needs a default.
    _patch_pool(monkeypatch, fake_pool)
    fake_conn.queue_fetch(
        [_chunk("chunk-a", "user-1", "text a")],
        [_neighbor("chunk-b", "note-old", "user-2", "text b", NEAR)],
    )
    _patch_model(
        monkeypatch, ['{"classification": "contradiction", "explanation": ""}']
    )

    await cd.detect_conflicts_for_note("note-new", "circle-1")

    explanation = fake_conn.statements_matching("INSERT INTO conflicts")[0][1][7]
    assert explanation


async def test_insert_is_idempotent_per_pair(monkeypatch, fake_conn, fake_pool):
    _patch_pool(monkeypatch, fake_pool)
    fake_conn.queue_fetch(
        [_chunk("chunk-a", "user-1", "text a")],
        [_neighbor("chunk-b", "note-old", "user-2", "text b", NEAR)],
    )
    _patch_model(monkeypatch, [CONTRADICTION])

    await cd.detect_conflicts_for_note("note-new", "circle-1")

    sql, _ = fake_conn.statements_matching("INSERT INTO conflicts")[0]
    assert "ON CONFLICT (chunk_a_id, chunk_b_id) DO NOTHING" in sql


async def test_strips_markdown_code_fence(monkeypatch, fake_conn, fake_pool):
    _patch_pool(monkeypatch, fake_pool)
    fake_conn.queue_fetch(
        [_chunk("chunk-a", "user-1", "text a")],
        [_neighbor("chunk-b", "note-old", "user-2", "text b", NEAR)],
    )
    _patch_model(monkeypatch, [f"```json\n{CONTRADICTION}\n```"])

    assert await cd.detect_conflicts_for_note("note-new", "circle-1") == 1


def test_strip_code_fence_passes_through_bare_json():
    assert cd._strip_code_fence('  {"classification":"agreement"} ') == (
        '{"classification":"agreement"}'
    )
