import types

from sync_graph.main import process_batch  # type: ignore


class DummyRecord:
    def __init__(self, value):
        self._value = value

    def value(self):
        return self._value


def test_process_batch_reads_payload(monkeypatch, tmp_path):
    ingest = tmp_path / "ingest.cypher"
    ingest.write_text("return 1", encoding="utf-8")

    session_calls = []

    class DummySession:
        def run(self, cypher, **params):
            session_calls.append(params)

    class DummyDriver:
        def session(self):
            return DummySession()

    rec = DummyRecord('{"userId":1}')
    process_batch([rec], DummyDriver(), str(ingest))
    assert session_calls
