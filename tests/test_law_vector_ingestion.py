"""법령 벡터 적재의 중복 방지·부분 실패·검색 준비 상태를 검증한다."""
import pytest
from sqlalchemy import select, func
from backend.tools.embed_property_laws import ingest_law, split_text, validate_vectors, DIMENSIONS
from db.base import session_scope
from db.models import LawCorpusDocument, LawCorpusChunk


def test_split_preserves_every_character():
    text = ("법령 본문\n" * 900) + "마지막"
    pieces = list(split_text(text))
    assert "".join(pieces) == text
    assert all(len(piece) <= 1000 for piece in pieces)


@pytest.mark.parametrize("vectors", [[], [[0] * DIMENSIONS], [[1, 2]], [[float('nan')] * DIMENSIONS]])
def test_invalid_vectors_fail(vectors):
    with pytest.raises(ValueError):
        validate_vectors(vectors, 1)


@pytest.fixture
def isolated_law_tables():
    from tests.conftest import truncate_tables
    truncate_tables(LawCorpusChunk, LawCorpusDocument)
    yield
    truncate_tables(LawCorpusChunk, LawCorpusDocument)


def test_resume_and_idempotence_keep_unfinished_document_inactive(isolated_law_tables):
    law = {"raw_sha256": "fixture", "law_id": "fixture", "law_name": "가상법", "effective_date": "20260101",
        "collected_at": "2026-09-10", "source_url": "https://example.invalid", "articles": [{
            "is_article": "조문", "number": "1", "branch_number": "", "title": "목적", "text": "가" * 2200}]}
    class FakeEmbedder:
        digest = 'test-only'
        calls = 0
        fail = True
        def embed(self, texts):
            self.calls += 1
            if self.fail and self.calls == 2:
                raise RuntimeError('model failure')
            return [[1.0] + [0.0] * (DIMENSIONS - 1) for _ in texts]
    embedder = FakeEmbedder()
    with pytest.raises(RuntimeError):
        ingest_law(law, embedder, batch_size=1)
    with session_scope() as session:
        doc = session.scalar(select(LawCorpusDocument))
        assert doc.status == 'loading' and not doc.active
        assert session.scalar(select(func.count()).select_from(LawCorpusChunk)) == 1
    embedder.fail = False
    result = ingest_law(law, embedder, batch_size=1)
    assert result['embedded'] == 2 and result['chunks'] == 3
    assert ingest_law(law, embedder)['embedded'] == 0
    with session_scope() as session:
        doc = session.scalar(select(LawCorpusDocument))
        assert doc.active and doc.status == 'ready'
        assert session.scalar(select(func.count()).select_from(LawCorpusChunk)) == 3
