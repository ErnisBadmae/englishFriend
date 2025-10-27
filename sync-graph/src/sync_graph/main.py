import json
import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from confluent_kafka import Consumer
from neo4j import GraphDatabase

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("sync-graph")

shutdown_event = threading.Event()

def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def build_consumer(cfg: Dict[str, Any]) -> Consumer:
    consumer = Consumer({
        "bootstrap.servers": ",".join(cfg["kafka"]["brokers"]),
        "group.id": cfg["kafka"]["group_id"],
        "enable.auto.commit": False,
        "auto.offset.reset": "earliest",
    })
    consumer.subscribe(cfg["kafka"]["topics"])
    return consumer


def _normalize_session_payload(value: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    source = value.get("source", {})
    if source.get("table") != "sessions":
        return None
    after = value.get("after") or {}
    session_id = after.get("id")
    user_id = after.get("user_id")
    started = after.get("started_at")
    if not all([session_id, user_id, started]):
        logger.warning(
            "Skipping session event due to missing required fields (id/user_id/started_at): %s",
            after,
        )
        return None
    return {
        "id": session_id,
        "user_id": user_id,
        "started_at": started,
        "ended_at": after.get("ended_at"),
        "lang_code": after.get("lang_code") or "en",
    }


def process_batch(records: List[Any], driver, ingest_script: str) -> None:
    if not records:
        return
    payloads = []
    for record in records:
        value = json.loads(record.value())
        logger.info("Processing event: %s", value.get("source", {}).get("table", "unknown"))
        normalized = _normalize_session_payload(value)
        if normalized:
            logger.info("Normalized payload: %s", normalized)
            payloads.append(normalized)
        else:
            logger.info("Skipped event (not a session)")
    with driver.session() as session:
        cypher = Path(ingest_script).read_text(encoding="utf-8")
        for payload in payloads:
            logger.info("Executing Cypher with payload: %s", payload)
            session.run(cypher, **payload)
    logger.info("Flushed %s session events", len(payloads))


def run_service(config_path: str) -> None:
    cfg = load_config(config_path)
    consumer = build_consumer(cfg)
    driver = GraphDatabase.driver(cfg["neo4j"]["uri"], auth=(cfg["neo4j"]["user"], cfg["neo4j"]["password"]))
    batch: List[Any] = []
    batch_size = cfg["kafka"].get("batch_size", 500)
    ingest_script = cfg["neo4j"]["ingest_script"]

    while not shutdown_event.is_set():
        msg = consumer.poll(timeout=cfg["kafka"].get("poll_timeout_ms", 500)/1000)
        if msg is None:
            process_batch(batch, driver, ingest_script)
            batch.clear()
            continue
        if msg.error():
            logger.error("Kafka error: %s", msg.error())
            continue
        batch.append(msg)
        if len(batch) >= batch_size:
            process_batch(batch, driver, ingest_script)
            consumer.commit(asynchronous=False)
            batch.clear()
    consumer.close()


def handle_shutdown(signum, frame):
    shutdown_event.set()


def main():
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    config_path = os.getenv("CONFIG_PATH", "sync-graph/config/app.example.yaml")
    if not os.path.exists(config_path):
        logger.error("Config not found: %s", config_path)
        sys.exit(1)
    run_service(config_path)


if __name__ == "__main__":
    main()
