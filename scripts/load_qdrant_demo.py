#!/usr/bin/env python3
"""
Load demo data into Qdrant for testing
"""

import json
import time
import requests
from datetime import datetime

QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "user_memories"

def wait_for_qdrant():
    """Wait for Qdrant to be ready"""
    for i in range(30):
        try:
            response = requests.get(f"{QDRANT_URL}/collections")
            if response.status_code == 200:
                print("Qdrant is ready!")
                return True
        except requests.exceptions.RequestException:
            pass
        print(f"Waiting for Qdrant... ({i+1}/30)")
        time.sleep(2)
    return False

def create_collection():
    """Create the user_memories collection"""
    collection_config = {
        "name": COLLECTION_NAME,
        "vectors": {
            "size": 1536,
            "distance": "Cosine"
        },
        "hnsw_config": {
            "m": 16,
            "ef_construct": 128
        },
        "optimizers_config": {
            "default_segment_number": 4,
            "memmap_threshold": 150000
        },
        "quantization_config": {
            "scalar": {
                "type": "int8",
                "always_ram": True
            }
        },
        "payload_schema": {
            "user_id": {"type": "integer"},
            "kind": {"type": "keyword"},
            "salience": {"type": "float"},
            "created_at": {"type": "integer"},
            "last_refreshed": {"type": "integer"},
            "emotion_code": {"type": "keyword"},
            "topic_ids": {"type": "keyword"},
            "source_session": {"type": "uuid"},
            "source_utterance": {"type": "uuid"}
        }
    }
    
    try:
        response = requests.put(
            f"{QDRANT_URL}/collections/{COLLECTION_NAME}",
            json=collection_config
        )
        if response.status_code in [200, 201]:
            print(f"Collection {COLLECTION_NAME} created successfully")
        elif response.status_code == 409:
            print(f"Collection {COLLECTION_NAME} already exists")
        else:
            print(f"Failed to create collection: {response.text}")
    except Exception as e:
        print(f"Error creating collection: {e}")

def load_demo_data():
    """Load demo data into Qdrant"""
    demo_points = [
        {
            "id": "00000000-0000-0000-0000-000000000030",
            "vector": [0.1] * 1536,  # Dummy vector
            "payload": {
                "user_id": 1,
                "kind": "episodic",
                "salience": 0.7,
                "created_at": int(datetime.now().timestamp()),
                "last_refreshed": int(datetime.now().timestamp()),
                "emotion_code": "joy",
                "topic_ids": ["11111111-1111-1111-1111-111111111111"],
                "source_session": "00000000-0000-0000-0000-000000000001",
                "source_utterance": "00000000-0000-0000-0000-000000000010"
            }
        },
        {
            "id": "00000000-0000-0000-0000-000000000031",
            "vector": [0.2] * 1536,  # Dummy vector
            "payload": {
                "user_id": 1,
                "kind": "semantic",
                "salience": 0.9,
                "created_at": int(datetime.now().timestamp()),
                "last_refreshed": int(datetime.now().timestamp()),
                "emotion_code": "calm",
                "topic_ids": ["11111111-1111-1111-1111-111111111111"],
                "source_session": "00000000-0000-0000-0000-000000000001",
                "source_utterance": "00000000-0000-0000-0000-000000000011"
            }
        },
        {
            "id": "00000000-0000-0000-0000-000000000032",
            "vector": [0.3] * 1536,  # Dummy vector
            "payload": {
                "user_id": 1,
                "kind": "episodic",
                "salience": 0.8,
                "created_at": int(datetime.now().timestamp()),
                "last_refreshed": int(datetime.now().timestamp()),
                "emotion_code": "joy",
                "topic_ids": ["22222222-2222-2222-2222-222222222222"],
                "source_session": "00000000-0000-0000-0000-000000000002",
                "source_utterance": "00000000-0000-0000-0000-000000000012"
            }
        }
    ]
    
    try:
        response = requests.put(
            f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points",
            json={"points": demo_points}
        )
        if response.status_code == 200:
            print(f"Loaded {len(demo_points)} demo points into Qdrant")
        else:
            print(f"Failed to load demo data: {response.text}")
    except Exception as e:
        print(f"Error loading demo data: {e}")

def main():
    """Main function"""
    print("Loading demo data into Qdrant...")
    
    if not wait_for_qdrant():
        print("Qdrant is not ready, exiting")
        return
    
    create_collection()
    load_demo_data()
    print("Demo data loading completed!")

if __name__ == "__main__":
    main()
