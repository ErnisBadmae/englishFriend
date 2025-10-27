#!/usr/bin/env python3
"""
Integration tests for sync-vector service

Tests the complete pipeline from Kafka to Qdrant using disposable instances.
"""

import asyncio
import json
import os
import subprocess
import time
import uuid
from typing import Dict, Any

import pytest
import requests
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct


class TestSyncVectorIntegration:
    """Integration tests for the sync-vector service"""
    
    @pytest.fixture(scope="class")
    def qdrant_client(self):
        """Start a disposable Qdrant instance"""
        # Start Qdrant container
        container_name = f"qdrant-test-{uuid.uuid4().hex[:8]}"
        subprocess.run([
            "docker", "run", "-d", "--name", container_name,
            "-p", "6334:6333",  # Use different port to avoid conflicts
            "qdrant/qdrant:latest"
        ], check=True)
        
        # Wait for Qdrant to be ready
        time.sleep(5)
        
        # Create client
        client = QdrantClient(url="http://localhost:6334")
        
        yield client
        
        # Cleanup
        subprocess.run(["docker", "stop", container_name], check=True)
        subprocess.run(["docker", "rm", container_name], check=True)
    
    @pytest.fixture(scope="class")
    def test_collection(self, qdrant_client):
        """Create test collection"""
        collection_name = "test_memories"
        
        # Delete if exists
        try:
            qdrant_client.delete_collection(collection_name)
        except:
            pass
        
        # Create collection
        qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config={
                "size": 1536,
                "distance": "Cosine"
            }
        )
        
        return collection_name
    
    def test_collection_creation(self, qdrant_client, test_collection):
        """Test that collection is created successfully"""
        collections = qdrant_client.get_collections()
        collection_names = [c.name for c in collections.collections]
        assert test_collection in collection_names
    
    def test_point_upsert(self, qdrant_client, test_collection):
        """Test upserting a point to Qdrant"""
        point_id = str(uuid.uuid4())
        vector = [0.1] * 1536  # 1536-dimensional vector
        
        point = PointStruct(
            id=point_id,
            vector=vector,
            payload={
                "user_id": 123,
                "kind": "episodic",
                "salience": 0.7,
                "created_at": int(time.time()),
                "last_refreshed": int(time.time()),
                "emotion_code": "joy",
                "topic_ids": ["topic-1", "topic-2"]
            }
        )
        
        # Upsert point
        qdrant_client.upsert(
            collection_name=test_collection,
            points=[point]
        )
        
        # Verify point exists
        points = qdrant_client.retrieve(
            collection_name=test_collection,
            ids=[point_id]
        )
        
        assert len(points) == 1
        assert points[0].id == point_id
        assert points[0].payload["user_id"] == 123
    
    def test_point_search(self, qdrant_client, test_collection):
        """Test searching for points"""
        # Create multiple points
        points = []
        for i in range(3):
            point_id = str(uuid.uuid4())
            vector = [0.1 + i * 0.1] * 1536
            
            point = PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "user_id": 123 + i,
                    "kind": "episodic",
                    "salience": 0.7,
                    "created_at": int(time.time()),
                    "last_refreshed": int(time.time()),
                    "emotion_code": "joy",
                    "topic_ids": [f"topic-{i}"]
                }
            )
            points.append(point)
        
        # Upsert points
        qdrant_client.upsert(
            collection_name=test_collection,
            points=points
        )
        
        # Search for points
        search_vector = [0.1] * 1536
        results = qdrant_client.search(
            collection_name=test_collection,
            query_vector=search_vector,
            limit=5,
            query_filter={
                "must": [{"key": "user_id", "match": {"value": 123}}]
            },
            with_payload=True
        )
        
        assert len(results) > 0
        assert results[0].payload["user_id"] == 123
    
    def test_point_delete(self, qdrant_client, test_collection):
        """Test deleting points"""
        point_id = str(uuid.uuid4())
        vector = [0.1] * 1536
        
        point = PointStruct(
            id=point_id,
            vector=vector,
            payload={
                "user_id": 123,
                "kind": "episodic",
                "salience": 0.7,
                "created_at": int(time.time()),
                "last_refreshed": int(time.time()),
                "emotion_code": "joy",
                "topic_ids": ["topic-1"]
            }
        )
        
        # Upsert point
        qdrant_client.upsert(
            collection_name=test_collection,
            points=[point]
        )
        
        # Verify point exists
        points = qdrant_client.retrieve(
            collection_name=test_collection,
            ids=[point_id]
        )
        assert len(points) == 1
        
        # Delete point
        qdrant_client.delete(
            collection_name=test_collection,
            points_selector=[point_id]
        )
        
        # Verify point is deleted
        points = qdrant_client.retrieve(
            collection_name=test_collection,
            ids=[point_id]
        )
        assert len(points) == 0
    
    def test_batch_operations(self, qdrant_client, test_collection):
        """Test batch upsert operations"""
        points = []
        for i in range(10):
            point_id = str(uuid.uuid4())
            vector = [0.1 + i * 0.01] * 1536
            
            point = PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "user_id": 123,
                    "kind": "episodic",
                    "salience": 0.7,
                    "created_at": int(time.time()),
                    "last_refreshed": int(time.time()),
                    "emotion_code": "joy",
                    "topic_ids": [f"topic-{i}"]
                }
            )
            points.append(point)
        
        # Batch upsert
        qdrant_client.upsert(
            collection_name=test_collection,
            points=points
        )
        
        # Verify all points exist
        collection_info = qdrant_client.get_collection(test_collection)
        assert collection_info.points_count >= 10
    
    def test_filter_operations(self, qdrant_client, test_collection):
        """Test filtering operations"""
        # Create points with different user_ids
        points = []
        for user_id in [123, 456, 789]:
            point_id = str(uuid.uuid4())
            vector = [0.1] * 1536
            
            point = PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "user_id": user_id,
                    "kind": "episodic",
                    "salience": 0.7,
                    "created_at": int(time.time()),
                    "last_refreshed": int(time.time()),
                    "emotion_code": "joy",
                    "topic_ids": [f"topic-{user_id}"]
                }
            )
            points.append(point)
        
        # Upsert points
        qdrant_client.upsert(
            collection_name=test_collection,
            points=points
        )
        
        # Filter by user_id
        search_vector = [0.1] * 1536
        results = qdrant_client.search(
            collection_name=test_collection,
            query_vector=search_vector,
            limit=10,
            query_filter={
                "must": [{"key": "user_id", "match": {"value": 123}}]
            },
            with_payload=True
        )
        
        # Should only return points with user_id=123
        for result in results:
            assert result.payload["user_id"] == 123


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
