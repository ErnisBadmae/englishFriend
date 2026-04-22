"""E2E Business Logic Tests.

This module provides end-to-end testing of the English Friend business logic
without requiring external hardware (microphone) or all external services.

Key features:
- Sequential node-based testing
- Clear reporting of where failures occur
- Mock database and external services
- Real business logic validation

Run with:
    python -m tests.e2e.test_business_flow
    pytest tests/e2e/ -v
    make test-e2e
"""
