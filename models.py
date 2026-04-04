"""
Pydantic v2 models for the Esports Tournament Operations Manager environment.
"""
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class Observation(BaseModel):
    """Environment observation containing tournament state information."""
    current_time: str = Field(..., description="Current tournament time in ISO format")
    active_alerts: List[str] = Field(default_factory=list, description="List of active alert messages")
    bracket_state: Dict[str, str] = Field(default_factory=dict, description="Match ID to winner ID or 'pending'")
    server_availability: Dict[str, bool] = Field(default_factory=dict, description="Server ID to availability status")
    prize_pool_status: Dict[str, float] = Field(default_factory=dict, description="Team ID to prize pool amount")
    scheduled_matches: Dict[str, str] = Field(default_factory=dict, description="Match ID to currently assigned server ID (e.g., {'M3': 'eu-west-2'})")


class Action(BaseModel):
    """Agent action containing tournament management commands."""
    update_matches: Optional[Dict[str, str]] = Field(None, description="Match ID to winner ID updates")
    reallocate_servers: Optional[Dict[str, str]] = Field(None, description="Match ID to server ID reallocation")
    broadcast_message: Optional[str] = Field(None, description="Broadcast message to send")
    adjust_prize_pool: Optional[Dict[str, float]] = Field(None, description="Team ID to prize pool adjustment")


class StepResponse(BaseModel):
    """Response from environment step containing observation, reward, and status."""
    observation: Observation = Field(..., description="Current environment observation")
    reward: float = Field(..., ge=0.0, le=1.0, description="Reward between 0.0 and 1.0")
    done: bool = Field(..., description="Whether the episode is complete")
    info: str = Field(..., description="Additional information about the step")