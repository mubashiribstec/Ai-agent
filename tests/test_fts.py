"""Full-text session search (FTS5) with ranking + LIKE fallback."""

from __future__ import annotations

from xplogent.memory.store import Store


def _seed(store):
    sid = store.create_session("chat")
    store.add_message(sid, "user", "how do I deploy the website to production")
    store.add_message(sid, "assistant", "run the build then push to the server")
    store.add_message(sid, "user", "what is my public ip address")
    return sid


def test_search_finds_relevant_message(tmp_path):
    store = Store(tmp_path / "m.db")
    _seed(store)
    hits = store.search_messages("deploy website")
    assert hits
    assert any("deploy the website" in h["content"] for h in hits)
    store.close()


def test_search_ranks_best_first(tmp_path):
    store = Store(tmp_path / "m.db")
    _seed(store)
    hits = store.search_messages("public ip")
    assert hits
    assert "public ip" in hits[0]["content"]
    store.close()


def test_delete_session_clears_index(tmp_path):
    store = Store(tmp_path / "m.db")
    sid = _seed(store)
    store.delete_session(sid)
    assert store.search_messages("deploy") == []
    store.close()


def test_like_fallback_when_no_fts(tmp_path):
    store = Store(tmp_path / "m.db")
    _seed(store)
    store._fts = False  # simulate a build without FTS5
    hits = store.search_messages("deploy")
    assert any("deploy" in h["content"] for h in hits)
    store.close()
