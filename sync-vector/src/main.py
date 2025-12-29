#!/usr/bin/env python3
"""
Sync-Vector Service: CDC to Qdrant Pipeline

Consumes Kafka messages from Debezium CDC and syncs memories to Qdrant vector database.
"""

import asyncio
import json
import logging
import os
import sys
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from aiohttp import web
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

import yaml
from kafka import KafkaConsumer
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Distance, VectorParams
from qdrant_client.http.exceptions import UnexpectedResponse


@dataclass
class Config:
    """Service configuration"""
    kafka_brokers: list[str]
    kafka_topic: str
    kafka_consumer_group: str
    kafka_dlq_topic: str
    kafka_max_poll_records: int
    
    qdrant_url: str
    qdrant_api_key: str
    qdrant_collection: str
    qdrant_vector_dim: int
    qdrant_batch_size: int
    qdrant_timeout_ms: int
    
    ingest_max_retries: int
    ingest_backoff_ms: int
    
    metrics_port: int
    log_level: str


class SyncVectorService:
    """Main service class for CDC to Qdrant synchronization"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = self._setup_logging()
        self.qdrant_client = None
        self.kafka_consumer = None
        self.app = None
        self.runner = None
        
        # Инициализация метрик Prometheus
        self.metrics_upsert_latency = Histogram(
            'sync_vector_upsert_latency_ms',
            'Латентность upsert операций в миллисекундах',
            buckets=[10, 50, 100, 150, 200, 500, 1000, 2000]
        )
        
        self.metrics_queue_lag = Gauge(
            'sync_vector_queue_lag',
            'Lag очереди Kafka в количестве сообщений'
        )
        
        self.metrics_failures_total = Counter(
            'sync_vector_failures_total',
            'Общее количество ошибок',
            ['reason']
        )
        
        self.metrics_last_success_timestamp = Gauge(
            'sync_vector_last_success_timestamp',
            'Timestamp последней успешной обработки'
        )
        
        self.metrics_messages_processed_total = Counter(
            'sync_vector_messages_processed_total',
            'Общее количество обработанных сообщений',
            ['status']  # 'success' или 'failure'
        )
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logging.basicConfig(
            level=getattr(logging, self.config.log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger('sync-vector')
    
    async def health_check(self, request):
        """Health check endpoint"""
        return web.json_response({"status": "healthy"})
    
    async def metrics_endpoint(self, request):
        """Prometheus metrics endpoint"""
        metrics_data = generate_latest().decode('utf-8')
        return web.Response(
            text=metrics_data,
            content_type='text/plain'
        )
    
    async def setup_http_server(self):
        """Setup HTTP server for health checks and metrics"""
        self.app = web.Application()
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/metrics', self.metrics_endpoint)
        
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        
        site = web.TCPSite(self.runner, '0.0.0.0', self.config.metrics_port)
        await site.start()
        self.logger.info(f"HTTP server started on port {self.config.metrics_port}")
    
    async def initialize(self):
        """Initialize connections to Kafka and Qdrant"""
        try:
            # Setup HTTP server first
            await self.setup_http_server()
            
            # Initialize Qdrant client
            self.qdrant_client = QdrantClient(
                url=self.config.qdrant_url,
                api_key=self.config.qdrant_api_key if self.config.qdrant_api_key else None,
                timeout=self.config.qdrant_timeout_ms / 1000
            )
            
            # Test Qdrant connection
            collections = self.qdrant_client.get_collections()
            self.logger.info(f"Connected to Qdrant. Collections: {len(collections.collections)}")
            
            # Initialize Kafka consumer
            self.kafka_consumer = KafkaConsumer(
                self.config.kafka_topic,
                bootstrap_servers=self.config.kafka_brokers,
                group_id=self.config.kafka_consumer_group,
                value_deserializer=lambda x: json.loads(x.decode('utf-8')),
                max_poll_records=self.config.kafka_max_poll_records,
                auto_offset_reset='earliest',
                enable_auto_commit=True
            )
            
            self.logger.info(f"Connected to Kafka topic: {self.config.kafka_topic}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize: {e}")
            raise
    
    def _transform_memory_to_point(self, memory_data: Dict[str, Any]) -> Optional[PointStruct]:
        """Transform a memory record to a Qdrant point"""
        try:
            # Extract vector from memory data (assuming it's in the payload)
            vector = memory_data.get('vector')
            if not vector or len(vector) != self.config.qdrant_vector_dim:
                self.logger.warning(f"Invalid vector dimension: {len(vector) if vector else 0}")
                return None
            
            # Extract payload data
            payload = memory_data.get('payload', {})
            
            # Create point
            point = PointStruct(
                id=memory_data.get('id'),
                vector=vector,
                payload={
                    'user_id': payload.get('user_id'),
                    'kind': payload.get('kind'),
                    'salience': payload.get('salience'),
                    'created_at': payload.get('created_at'),
                    'last_refreshed': payload.get('last_refreshed'),
                    'emotion_code': payload.get('emotion_code'),
                    'topic_ids': payload.get('topic_ids', []),
                    'source_session': payload.get('source_session'),
                    'source_utterance': payload.get('source_utterance')
                }
            )
            
            return point
            
        except Exception as e:
            self.logger.error(f"Failed to transform memory to point: {e}")
            return None
    
    async def process_memory_batch(self, messages: list) -> int:
        """Process a batch of memory messages"""
        points = []
        processed = 0
        
        for message in messages:
            try:
                point = self._transform_memory_to_point(message.value)
                if point:
                    points.append(point)
                    processed += 1
            except Exception as e:
                self.logger.error(f"Failed to process message: {e}")
                self.metrics_failures_total.labels(reason='transform').inc()
                self.metrics_messages_processed_total.labels(status='failure').inc()
                # TODO: Send to DLQ
        
        if points:
            try:
                # Upsert points to Qdrant с измерением времени
                start_time = time.time()
                self.qdrant_client.upsert(
                    collection_name=self.config.qdrant_collection,
                    points=points
                )
                duration_ms = (time.time() - start_time) * 1000
                
                # Записываем метрики
                self.metrics_upsert_latency.observe(duration_ms)
                self.metrics_last_success_timestamp.set(time.time())
                self.metrics_messages_processed_total.labels(status='success').inc(processed)
                
                self.logger.info(f"Upserted {len(points)} points to Qdrant in {duration_ms:.2f}ms")
            except Exception as e:
                self.logger.error(f"Failed to upsert points: {e}")
                self.metrics_failures_total.labels(reason='qdrant').inc()
                self.metrics_messages_processed_total.labels(status='failure').inc(len(points))
                # TODO: Implement retry logic and DLQ
        
        return processed
    
    async def run(self):
        """Main service loop"""
        self.logger.info("Starting sync-vector service...")
        
        try:
            while True:
                # Poll for messages
                message_batch = self.kafka_consumer.poll(timeout_ms=1000)
                
                if message_batch:
                    for topic_partition, messages in message_batch.items():
                        processed = await self.process_memory_batch(messages)
                        self.logger.info(f"Processed {processed} messages from {topic_partition}")
                        
                        # Обновляем lag метрику (примерная оценка)
                        try:
                            # Получаем позиции consumer для оценки lag
                            partition = topic_partition
                            consumer_position = self.kafka_consumer.position(partition)
                            # Для точного lag нужно получить end offset, упрощенная версия
                            # В реальности лучше использовать kafka-python admin client
                            # Пока оставляем упрощенную версию
                            self.metrics_queue_lag.set(0)  # Плейсхолдер
                        except Exception:
                            pass  # Игнорируем ошибки при получении lag
                
                # Small delay to prevent busy waiting
                await asyncio.sleep(0.1)
                
        except KeyboardInterrupt:
            self.logger.info("Shutting down...")
        except Exception as e:
            self.logger.error(f"Service error: {e}")
            raise
        finally:
            if self.kafka_consumer:
                self.kafka_consumer.close()


def load_config(config_path: str) -> Config:
    """Load configuration from YAML file"""
    with open(config_path, 'r') as f:
        config_data = yaml.safe_load(f)
    
    return Config(
        kafka_brokers=config_data['kafka']['brokers'],
        kafka_topic=config_data['kafka']['topic'],
        kafka_consumer_group=config_data['kafka']['consumer_group'],
        kafka_dlq_topic=config_data['kafka']['dlq_topic'],
        kafka_max_poll_records=config_data['kafka']['max_poll_records'],
        
        qdrant_url=config_data['qdrant']['url'],
        qdrant_api_key=config_data['qdrant']['api_key'],
        qdrant_collection=config_data['qdrant']['collection'],
        qdrant_vector_dim=config_data['qdrant']['vector_dim'],
        qdrant_batch_size=config_data['qdrant']['batch_size'],
        qdrant_timeout_ms=config_data['qdrant']['timeout_ms'],
        
        ingest_max_retries=config_data['ingest']['max_retries'],
        ingest_backoff_ms=config_data['ingest']['backoff_ms'],
        
        metrics_port=config_data['observability']['metrics_port'],
        log_level=config_data['observability']['log_level']
    )


async def main():
    """Main entry point"""
    config_path = os.getenv('CONFIG_PATH', 'sync-vector/config/app.yaml')
    
    if not os.path.exists(config_path):
        print(f"Configuration file not found: {config_path}")
        print("Please create a configuration file based on sync-vector/config/app.example.yaml")
        sys.exit(1)
    
    config = load_config(config_path)
    service = SyncVectorService(config)
    
    await service.initialize()
    await service.run()


if __name__ == '__main__':
    asyncio.run(main())
