from sync_graph.main import load_config  # type: ignore


def test_config_load(tmp_path):
    cfg_path = tmp_path / "app.yaml"
    cfg_path.write_text("kafka:\n  brokers: ['kafka:9092']\n  group_id: test\n  topics: []\nneo4j:\n  uri: bolt://neo4j:7687\n  user: neo4j\n  password: pass\n", encoding="utf-8")
    cfg = load_config(str(cfg_path))
    assert cfg["kafka"]["group_id"] == "test"
