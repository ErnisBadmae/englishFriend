"""Response mapping helpers to reduce code duplication in API endpoints.

These functions convert database models to Pydantic response schemas,
eliminating repetitive field mapping code across multiple endpoints.
"""

from typing import List
from app.schemas.additional_schemas import (
    UserInterestResponse,
    UserInterestListResponse,
    MemoryResponse,
    MemoryListResponse,
    XPEventResponse,
    XPEventListResponse,
    LearningPlanResponse,
)


def map_interest_to_response(interest) -> UserInterestResponse:
    """Convert UserInterest model to response schema."""
    return UserInterestResponse(
        user_id=interest.user_id,
        topic_id=interest.topic_id,
        weight=interest.weight,
        last_mentioned=interest.last_mentioned
    )


def map_interests_to_list_response(interests: List) -> UserInterestListResponse:
    """Convert list of UserInterest models to list response."""
    return UserInterestListResponse(
        interests=[map_interest_to_response(interest) for interest in interests],
        total=len(interests)
    )


def map_memory_to_response(memory) -> MemoryResponse:
    """Convert Memory model to response schema."""
    return MemoryResponse(
        id=memory.id,
        user_id=memory.user_id,
        kind=memory.kind,
        content=memory.content,
        meta=memory.meta,
        salience=memory.salience,
        created_at=memory.created_at,
        last_refreshed=memory.last_refreshed
    )


def map_memories_to_list_response(memories: List) -> MemoryListResponse:
    """Convert list of Memory models to list response."""
    return MemoryListResponse(
        memories=[map_memory_to_response(memory) for memory in memories],
        total=len(memories)
    )


def map_xp_event_to_response(event) -> XPEventResponse:
    """Convert XPEvent model to response schema."""
    return XPEventResponse(
        id=event.id,
        user_id=event.user_id,
        session_id=event.session_id,
        kind=event.kind,
        points=event.points,
        happened_at=event.happened_at
    )


def map_xp_events_to_list_response(events: List) -> XPEventListResponse:
    """Convert list of XPEvent models to list response."""
    return XPEventListResponse(
        events=[map_xp_event_to_response(event) for event in events],
        total=len(events)
    )


def map_learning_plan_to_response(plan) -> LearningPlanResponse:
    """Convert LearningPlan model to response schema."""
    return LearningPlanResponse(
        id=plan.id,
        user_id=plan.user_id,
        level_target=plan.level_target,
        next_review_at=plan.next_review_at,
        roadmap=plan.roadmap,
        updated_at=plan.updated_at
    )
