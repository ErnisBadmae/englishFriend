#!/usr/bin/env python3
"""
Automated test for the manual validation checklist

This script automates the manual testing steps described in sync-vector/docs/testing.md
"""

import json
import subprocess
import time
import uuid
from typing import Dict, Any

import requests
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct


class ManualChecklistTester:
    """Automated tester for the manual validation checklist"""
    
    def __init__(self, qdrant_url: str = "http://localhost:6333"):
        self.qdrant_url = qdrant_url
        self.client = QdrantClient(url=qdrant_url)
        self.collection_name = "user_memories"
    
    def test_1_local_qdrant_bringup(self):
        """Test 1: Local Qdrant bring-up"""
        print("1. Testing local Qdrant bring-up...")
        
        try:
            # Test connection
            collections = self.client.get_collections()
            print(f"✓ Connected to Qdrant. Collections: {len(collections.collections)}")
            return True
        except Exception as e:
            print(f"✗ Failed to connect to Qdrant: {e}")
            return False
    
    def test_2_apply_schema(self):
        """Test 2: Apply schema"""
        print("2. Testing schema application...")
        
        try:
            # Delete collection if exists
            try:
                self.client.delete_collection(self.collection_name)
                print("✓ Deleted existing collection")
            except:
                print("✓ No existing collection to delete")
            
            # Create collection using schema
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    "size": 1536,
                    "distance": "Cosine"
                },
                hnsw_config={
                    "m": 16,
                    "ef_construct": 128
                },
                optimizers_config={
                    "default_segment_number": 4,
                    "memmap_threshold": 150000
                },
                quantization_config={
                    "scalar": {
                        "type": "int8",
                        "always_ram": True
                    }
                }
            )
            
            print("✓ Collection created successfully")
            return True
        except Exception as e:
            print(f"✗ Failed to create collection: {e}")
            return False
    
    def test_3_seed_sample_point(self):
        """Test 3: Seed sample point"""
        print("3. Testing sample point insertion...")
        
        try:
            # Create sample point
            point_id = "11111111-1111-1111-1111-111111111111"
            vector = [0.01 + i * 0.01 for i in range(1536)]  # 1536-dimensional vector
            
            point = PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "user_id": 123,
                    "kind": "episodic",
                    "salience": 0.7,
                    "created_at": 1730000000,
                    "last_refreshed": 1730000500,
                    "emotion_code": "joy",
                    "topic_ids": ["22222222-2222-2222-2222-222222222222"]
                }
            )
            
            # Upsert point
            self.client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
            
            print("✓ Sample point inserted successfully")
            return True
        except Exception as e:
            print(f"✗ Failed to insert sample point: {e}")
            return False
    
    def test_4_query_verification(self):
        """Test 4: Query verification"""
        print("4. Testing query verification...")
        
        try:
            # Create search vector
            search_vector = [0.01 + i * 0.01 for i in range(1536)]
            
            # Search for points
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=search_vector,
                limit=5,
                query_filter={
                    "must": [{"key": "user_id", "match": {"value": 123}}]
                },
                with_payload=True
            )
            
            if len(results) > 0:
                result = results[0]
                print(f"✓ Found {len(results)} results")
                print(f"  - Point ID: {result.id}")
                print(f"  - User ID: {result.payload.get('user_id')}")
                print(f"  - Kind: {result.payload.get('kind')}")
                print(f"  - Salience: {result.payload.get('salience')}")
                return True
            else:
                print("✗ No results found")
                return False
        except Exception as e:
            print(f"✗ Failed to query points: {e}")
            return False
    
    def test_5_delete_test(self):
        """Test 5: Delete test"""
        print("5. Testing point deletion...")
        
        try:
            point_id = "11111111-1111-1111-1111-111111111111"
            
            # Delete point
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=[point_id]
            )
            
            print("✓ Point deleted successfully")
            
            # Verify deletion
            search_vector = [0.01 + i * 0.01 for i in range(1536)]
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=search_vector,
                limit=5,
                query_filter={
                    "must": [{"key": "user_id", "match": {"value": 123}}]
                },
                with_payload=True
            )
            
            if len(results) == 0:
                print("✓ Deletion verified - no results found")
                return True
            else:
                print(f"✗ Deletion failed - {len(results)} results still found")
                return False
        except Exception as e:
            print(f"✗ Failed to delete point: {e}")
            return False
    
    def test_6_cdc_replay_dry_run(self):
        """Test 6: CDC replay dry run"""
        print("6. Testing CDC replay dry run...")
        
        try:
            # Create mock Kafka message payload
            mock_message = {
                "id": "22222222-2222-2222-2222-222222222222",
                "vector": [0.02 + i * 0.01 for i in range(1536)],
                "payload": {
                    "user_id": 456,
                    "kind": "semantic",
                    "salience": 0.8,
                    "created_at": 1730001000,
                    "last_refreshed": 1730001500,
                    "emotion_code": "neutral",
                    "topic_ids": ["33333333-3333-3333-3333-333333333333"],
                    "source_session": "44444444-4444-4444-4444-444444444444",
                    "source_utterance": "55555555-5555-5555-5555-555555555555"
                }
            }
            
            # Transform to Qdrant point
            point = PointStruct(
                id=mock_message["id"],
                vector=mock_message["vector"],
                payload=mock_message["payload"]
            )
            
            # Upsert point
            self.client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
            
            # Verify point exists
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=mock_message["vector"],
                limit=1,
                query_filter={
                    "must": [{"key": "user_id", "match": {"value": 456}}]
                },
                with_payload=True
            )
            
            if len(results) > 0:
                print("✓ CDC replay dry run successful")
                print(f"  - Point ID: {results[0].id}")
                print(f"  - User ID: {results[0].payload.get('user_id')}")
                return True
            else:
                print("✗ CDC replay dry run failed - point not found")
                return False
        except Exception as e:
            print(f"✗ CDC replay dry run failed: {e}")
            return False
    
    def run_all_tests(self):
        """Run all manual checklist tests"""
        print("Running automated manual validation checklist...")
        print("=" * 50)
        
        tests = [
            self.test_1_local_qdrant_bringup,
            self.test_2_apply_schema,
            self.test_3_seed_sample_point,
            self.test_4_query_verification,
            self.test_5_delete_test,
            self.test_6_cdc_replay_dry_run
        ]
        
        passed = 0
        total = len(tests)
        
        for test in tests:
            try:
                if test():
                    passed += 1
                print()
            except Exception as e:
                print(f"✗ Test failed with exception: {e}")
                print()
        
        print("=" * 50)
        print(f"Results: {passed}/{total} tests passed")
        
        if passed == total:
            print("✓ All tests passed! Manual validation checklist completed successfully.")
            return True
        else:
            print("✗ Some tests failed. Please check the output above.")
            return False


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run automated manual validation checklist")
    parser.add_argument("--qdrant-url", default="http://localhost:6333", 
                       help="Qdrant URL (default: http://localhost:6333)")
    
    args = parser.parse_args()
    
    tester = ManualChecklistTester(args.qdrant_url)
    success = tester.run_all_tests()
    
    exit(0 if success else 1)


if __name__ == '__main__':
    main()
