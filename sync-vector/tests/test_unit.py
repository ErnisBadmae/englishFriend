#!/usr/bin/env python3
"""
Unit tests for sync-vector service

Tests individual components without external dependencies.
"""

import json
import pytest
from unittest.mock import Mock, patch

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from main import SyncVectorService, Config, load_config


class TestConfig:
    """Test configuration loading"""
    
    def test_load_config(self, tmp_path):
        """Test loading configuration from YAML file"""
        config_data = {
            'kafka': {
                'brokers': ['localhost:9092'],
                'topic': 'memories_public',
                'consumer_group': 'sync-vector',
                'dlq_topic': 'vector_failures',
                'max_poll_records': 500
            },
            'qdrant': {
                'url': 'http://localhost:6333',
                'api_key': '',
                'collection': 'user_memories',
                'vector_dim': 1536,
                'batch_size': 64,
                'timeout_ms': 2000
            },
            'ingest': {
                'max_retries': 5,
                'backoff_ms': 250
            },
            'observability': {
                'metrics_port': 8090,
                'log_level': 'info'
            }
        }
        
        config_file = tmp_path / "config.yaml"
        with open(config_file, 'w') as f:
            import yaml
            yaml.dump(config_data, f)
        
        config = load_config(str(config_file))
        
        assert config.kafka_brokers == ['localhost:9092']
        assert config.kafka_topic == 'memories_public'
        assert config.qdrant_url == 'http://localhost:6333'
        assert config.qdrant_collection == 'user_memories'
        assert config.qdrant_vector_dim == 1536


class TestSyncVectorService:
    """Test the main service class"""
    
    @pytest.fixture
    def config(self):
        """Create a test configuration"""
        return Config(
            kafka_brokers=['localhost:9092'],
            kafka_topic='memories_public',
            kafka_consumer_group='sync-vector',
            kafka_dlq_topic='vector_failures',
            kafka_max_poll_records=500,
            qdrant_url='http://localhost:6333',
            qdrant_api_key='',
            qdrant_collection='user_memories',
            qdrant_vector_dim=1536,
            qdrant_batch_size=64,
            qdrant_timeout_ms=2000,
            ingest_max_retries=5,
            ingest_backoff_ms=250,
            metrics_port=8090,
            log_level='info'
        )
    
    @pytest.fixture
    def service(self, config):
        """Create a test service instance"""
        return SyncVectorService(config)
    
    def test_service_initialization(self, service):
        """Test service initialization"""
        assert service.config is not None
        assert service.logger is not None
        assert service.qdrant_client is None
        assert service.kafka_consumer is None
    
    def test_transform_memory_to_point_valid(self, service):
        """Test transforming a valid memory to a Qdrant point"""
        memory_data = {
            'id': 'test-id',
            'vector': [0.1] * 1536,
            'payload': {
                'user_id': 123,
                'kind': 'episodic',
                'salience': 0.7,
                'created_at': 1730000000,
                'last_refreshed': 1730000500,
                'emotion_code': 'joy',
                'topic_ids': ['topic-1'],
                'source_session': 'session-1',
                'source_utterance': 'utterance-1'
            }
        }
        
        point = service._transform_memory_to_point(memory_data)
        
        assert point is not None
        assert point.id == 'test-id'
        assert len(point.vector) == 1536
        assert point.payload['user_id'] == 123
        assert point.payload['kind'] == 'episodic'
        assert point.payload['salience'] == 0.7
    
    def test_transform_memory_to_point_invalid_vector(self, service):
        """Test transforming a memory with invalid vector"""
        memory_data = {
            'id': 'test-id',
            'vector': [0.1] * 100,  # Wrong dimension
            'payload': {
                'user_id': 123,
                'kind': 'episodic'
            }
        }
        
        point = service._transform_memory_to_point(memory_data)
        
        assert point is None
    
    def test_transform_memory_to_point_missing_vector(self, service):
        """Test transforming a memory without vector"""
        memory_data = {
            'id': 'test-id',
            'payload': {
                'user_id': 123,
                'kind': 'episodic'
            }
        }
        
        point = service._transform_memory_to_point(memory_data)
        
        assert point is None
    
    def test_transform_memory_to_point_malformed_data(self, service):
        """Test transforming malformed memory data"""
        memory_data = {
            'id': 'test-id',
            'vector': [0.1] * 1536,
            'payload': None  # Malformed payload
        }
        
        point = service._transform_memory_to_point(memory_data)
        
        assert point is None
    
    @pytest.mark.asyncio
    async def test_process_memory_batch_empty(self, service):
        """Test processing an empty batch"""
        processed = await service.process_memory_batch([])
        assert processed == 0
    
    @pytest.mark.asyncio
    async def test_process_memory_batch_valid(self, service):
        """Test processing a valid batch"""
        # Mock Qdrant client
        mock_client = Mock()
        service.qdrant_client = mock_client
        
        messages = [
            Mock(value={
                'id': 'test-id-1',
                'vector': [0.1] * 1536,
                'payload': {
                    'user_id': 123,
                    'kind': 'episodic',
                    'salience': 0.7,
                    'created_at': 1730000000,
                    'last_refreshed': 1730000500,
                    'emotion_code': 'joy',
                    'topic_ids': ['topic-1']
                }
            }),
            Mock(value={
                'id': 'test-id-2',
                'vector': [0.2] * 1536,
                'payload': {
                    'user_id': 456,
                    'kind': 'semantic',
                    'salience': 0.8,
                    'created_at': 1730000000,
                    'last_refreshed': 1730000500,
                    'emotion_code': 'neutral',
                    'topic_ids': ['topic-2']
                }
            })
        ]
        
        processed = await service.process_memory_batch(messages)
        
        assert processed == 2
        mock_client.upsert.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_memory_batch_mixed_valid_invalid(self, service):
        """Test processing a batch with both valid and invalid messages"""
        # Mock Qdrant client
        mock_client = Mock()
        service.qdrant_client = mock_client
        
        messages = [
            Mock(value={
                'id': 'test-id-1',
                'vector': [0.1] * 1536,  # Valid
                'payload': {
                    'user_id': 123,
                    'kind': 'episodic'
                }
            }),
            Mock(value={
                'id': 'test-id-2',
                'vector': [0.1] * 100,  # Invalid dimension
                'payload': {
                    'user_id': 456,
                    'kind': 'semantic'
                }
            }),
            Mock(value={
                'id': 'test-id-3',
                'vector': [0.3] * 1536,  # Valid
                'payload': {
                    'user_id': 789,
                    'kind': 'episodic'
                }
            })
        ]
        
        processed = await service.process_memory_batch(messages)
        
        assert processed == 2  # Only valid messages processed
        mock_client.upsert.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_memory_batch_qdrant_error(self, service):
        """Test handling Qdrant errors during batch processing"""
        # Mock Qdrant client to raise an exception
        mock_client = Mock()
        mock_client.upsert.side_effect = Exception("Qdrant connection failed")
        service.qdrant_client = mock_client
        
        messages = [
            Mock(value={
                'id': 'test-id-1',
                'vector': [0.1] * 1536,
                'payload': {
                    'user_id': 123,
                    'kind': 'episodic'
                }
            })
        ]
        
        processed = await service.process_memory_batch(messages)
        
        assert processed == 1  # Message was processed but upsert failed
        mock_client.upsert.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
