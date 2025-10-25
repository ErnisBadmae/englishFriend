#!/bin/bash
set -euo pipefail

echo "Running sync-vector tests..."

# Install test dependencies
pip install pytest pytest-asyncio pytest-mock

# Run unit tests
echo "Running unit tests..."
python -m pytest sync-vector/tests/test_unit.py -v

# Run integration tests (requires Docker)
echo "Running integration tests..."
python -m pytest sync-vector/tests/test_integration.py -v

echo "All tests completed!"
