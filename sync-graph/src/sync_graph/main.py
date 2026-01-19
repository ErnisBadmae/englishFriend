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
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST, REGISTRY
from aiohttp import web
import asyncio

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("sync-graph")

shutdown_event = threading.Event()

# Инициализация метрик с проверкой дублирования
_metrics_initialized = False

# Глобальные переменные для метрик (инициализируются в _init_metrics_once)
metrics_batch_duration = None
metrics_dlq_total = None
metrics_last_success_timestamp = None
metrics_nodes_created_total = None
metrics_relationships_created_total = None

def _init_metrics_once():
    """Инициализировать метрики только один раз"""
    global _metrics_initialized, metrics_batch_duration, metrics_dlq_total
    global metrics_last_success_timestamp, metrics_nodes_created_total, metrics_relationships_created_total
    
    if _metrics_initialized:
        return  # Метрики уже созданы
    
    # Проверяем, не зарегистрированы ли уже метрики
    try:
        existing_names = set()
        for collector, names in REGISTRY._collector_to_names.items():
            existing_names.update(names)
        if 'sync_graph_batch_duration_ms' in existing_names:
            _metrics_initialized = True
            return
    except Exception:
        pass  # Если не можем проверить, создадим метрики

    # Создаем метрики
    metrics_batch_duration = Histogram(
        'sync_graph_batch_duration_ms',
        'Длительность обработки батча в миллисекундах',
        buckets=[10, 50, 100, 250, 500, 1000, 2000, 5000]
    )
    
    metrics_dlq_total = Counter(
        'sync_graph_dlq_total',
        'Общее количество сообщений отправленных в DLQ',
        ['reason']
    )
    
    metrics_last_success_timestamp = Gauge(
        'sync_graph_last_success_timestamp',
        'Timestamp последней успешной обработки батча'
    )
    
    metrics_nodes_created_total = Counter(
        'sync_graph_nodes_created_total',
        'Общее количество созданных узлов',
        ['label']
    )
    
    metrics_relationships_created_total = Counter(
        'sync_graph_relationships_created_total',
        'Общее количество созданных связей',
        ['type']
    )
    
    _metrics_initialized = True

# Инициализируем метрики при импорте модуля
_init_metrics_once()


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
    """Обработка батча записей с метриками"""
    if not records:
        return
    
    start_time = time.time()
    payloads = []
    nodes_created = 0
    relationships_created = 0
    
    try:
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
                result = session.run(cypher, **payload)
                # Подсчитываем созданные узлы и связи (упрощенная оценка)
                # В реальности нужно парсить результат Cypher
                nodes_created += 1  # Примерно по одному узлу на сессию
                relationships_created += 1  # Примерно по одной связи
        
        # Записываем метрики успеха
        duration_ms = (time.time() - start_time) * 1000
        if metrics_batch_duration is not None:
            metrics_batch_duration.observe(duration_ms)
        if metrics_last_success_timestamp is not None:
            metrics_last_success_timestamp.set(time.time())
        if metrics_nodes_created_total is not None:
            metrics_nodes_created_total.labels(label='Session').inc(nodes_created)
        if metrics_relationships_created_total is not None:
            metrics_relationships_created_total.labels(type='PARTICIPATED_IN').inc(relationships_created)
        
        logger.info("Flushed %s session events in %.2fms", len(payloads), duration_ms)
    except Exception as e:
        logger.error("Error processing batch: %s", e)
        if metrics_dlq_total is not None:
            metrics_dlq_total.labels(reason='processing_error').inc(len(records))
        raise


def run_http_server(port: int) -> None:
    """Запуск HTTP сервера для метрик в отдельном потоке"""
    async def setup_server():
        app = web.Application()
        
        async def health_check(request):
            return web.json_response({"status": "healthy"})
        
        async def metrics_endpoint(request):
            """Prometheus metrics endpoint"""
            metrics_data = generate_latest().decode('utf-8')
            return web.Response(
                text=metrics_data,
                content_type='text/plain'
            )
        
        app.router.add_get('/health', health_check)
        app.router.add_get('/metrics', metrics_endpoint)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        logger.info(f"HTTP server started on port {port}")
        
        # Держим сервер запущенным
        try:
            await asyncio.Event().wait()
        except (KeyboardInterrupt, SystemExit):
            await runner.cleanup()
    
    asyncio.run(setup_server())


def run_service(config_path: str) -> None:
    cfg = load_config(config_path)
    
    # Убеждаемся что метрики инициализированы
    _init_metrics_once()
    
    consumer = build_consumer(cfg)
    driver = GraphDatabase.driver(cfg["neo4j"]["uri"], auth=(cfg["neo4j"]["user"], cfg["neo4j"]["password"]))
    batch: List[Any] = []
    batch_size = cfg["kafka"].get("batch_size", 500)
    ingest_script = cfg["neo4j"]["ingest_script"]
    
    # Запускаем HTTP сервер в отдельном потоке
    metrics_port = cfg.get("observability", {}).get("metrics_port", 8091)
    http_thread = threading.Thread(
        target=run_http_server,
        args=(metrics_port,),
        daemon=True
    )
    http_thread.start()

    while not shutdown_event.is_set():
        msg = consumer.poll(timeout=cfg["kafka"].get("poll_timeout_ms", 500)/1000)
        if msg is None:
            process_batch(batch, driver, ingest_script)
            batch.clear()
            continue
        if msg.error():
            logger.error("Kafka error: %s", msg.error())
            if metrics_dlq_total is not None:
                metrics_dlq_total.labels(reason='kafka_error').inc()
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
