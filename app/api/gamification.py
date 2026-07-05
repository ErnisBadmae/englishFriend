"""Gamification API endpoints.

Provides endpoints for:
- User stats (XP, level, streak)
- Leaderboard (future)
- Achievements (future)
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from app.core.deps import get_db
from app.services.gamification import XPService, StreakService
from app.models.core_tables import User


router = APIRouter(prefix="/gamification", tags=["gamification"])


# ============== Schemas ==============

class XPInfo(BaseModel):
    """XP information."""
    total: int
    level: int
    current_level_xp: int
    next_level_xp: int
    progress: float


class StreakInfo(BaseModel):
    """Streak information."""
    current: int
    max: int
    at_risk: bool
    last_activity: Optional[str]


class TodayStats(BaseModel):
    """Today's statistics."""
    xp_earned: int
    sessions: int  # Future: count from sessions table


class UserStats(BaseModel):
    """Complete user gamification stats."""
    user_id: int
    xp: XPInfo
    streak: StreakInfo
    today: TodayStats


class XPHistory(BaseModel):
    """XP history entry."""
    date: str
    xp: int


# ============== Endpoints ==============

@router.get("/users/{user_id}/stats", response_model=UserStats)
async def get_user_stats(
    user_id: int,
    db: AsyncSession = Depends(get_db),
) -> UserStats:
    """Get complete gamification stats for a user.

    Returns XP, level, streak, and today's activity.
    """
    # Verify user exists
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    xp_service = XPService(db)
    streak_service = StreakService(db)

    # Get XP info
    level_info = await xp_service.get_level_info(user_id)
    xp_info = XPInfo(
        total=level_info["total_xp"],
        level=level_info["level"],
        current_level_xp=level_info["current_level_xp"],
        next_level_xp=level_info["next_level_xp"],
        progress=level_info["progress"],
    )

    # Get streak info
    streak_info_dict = await streak_service.get_streak_info(user_id)
    streak_info = StreakInfo(
        current=streak_info_dict["current"],
        max=streak_info_dict["max"],
        at_risk=streak_info_dict["at_risk"],
        last_activity=streak_info_dict["last_activity"],
    )

    # Get today's XP
    today_xp = await xp_service.get_today_xp(user_id)
    today_stats = TodayStats(
        xp_earned=today_xp,
        sessions=0,  # TODO: Count from sessions table
    )

    return UserStats(
        user_id=user_id,
        xp=xp_info,
        streak=streak_info,
        today=today_stats,
    )


@router.get("/users/{user_id}/xp/history", response_model=list[XPHistory])
async def get_xp_history(
    user_id: int,
    days: int = 7,
    db: AsyncSession = Depends(get_db),
) -> list[XPHistory]:
    """Get XP history for the last N days.

    Args:
        user_id: User ID
        days: Number of days to look back (default 7, max 30)
    """
    # Limit days to prevent abuse
    days = min(days, 30)

    # Verify user exists
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    xp_service = XPService(db)
    history = await xp_service.get_xp_history(user_id, days)

    return [XPHistory(date=h["date"], xp=h["xp"]) for h in history]


@router.post("/users/{user_id}/check-in")
async def check_in(
    user_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Register user activity (check-in).

    This updates the streak counter.
    Usually called automatically when a session ends.

    Returns:
        Streak info including whether it was extended, new record, etc.
    """
    # Verify user exists
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    streak_service = StreakService(db)
    result = await streak_service.check_in(user_id)

    return result


@router.get("/users/{user_id}/streak")
async def get_streak(
    user_id: int,
    db: AsyncSession = Depends(get_db),
) -> StreakInfo:
    """Get streak information for a user."""
    # Verify user exists
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    streak_service = StreakService(db)
    streak_info_dict = await streak_service.get_streak_info(user_id)

    return StreakInfo(
        current=streak_info_dict["current"],
        max=streak_info_dict["max"],
        at_risk=streak_info_dict["at_risk"],
        last_activity=streak_info_dict["last_activity"],
    )


@router.get("/users/{user_id}/level")
async def get_level(
    user_id: int,
    db: AsyncSession = Depends(get_db),
) -> XPInfo:
    """Get level information for a user."""
    # Verify user exists
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    xp_service = XPService(db)
    level_info = await xp_service.get_level_info(user_id)

    return XPInfo(
        total=level_info["total_xp"],
        level=level_info["level"],
        current_level_xp=level_info["current_level_xp"],
        next_level_xp=level_info["next_level_xp"],
        progress=level_info["progress"],
    )
