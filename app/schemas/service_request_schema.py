from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict

from pydantic import BaseModel, ConfigDict, Field


class ServiceRequestCreate(BaseModel):
    requested_date: Optional[datetime] = None
    budget: Optional[Decimal] = None
    location: Optional[str] = Field(default=None, max_length=180)
    notes: Optional[str] = Field(default=None, max_length=2000)


class ServiceRequestResponse(BaseModel):
    id: str
    service_id: int
    requester_user_id: int
    provider_user_id: Optional[int]
    status: str
    priority: str
    requested_date: Optional[datetime]
    budget: Optional[Decimal]
    location: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    service: Optional[Dict] = None
    requester: Optional[Dict] = None
    provider: Optional[Dict] = None

    model_config = ConfigDict(from_attributes=True)


class ServiceRequestStatusUpdate(BaseModel):
    status: str = Field(..., min_length=3, max_length=20)
    note: Optional[str] = Field(default=None, max_length=1200)
    scheduled_date: Optional[datetime] = None