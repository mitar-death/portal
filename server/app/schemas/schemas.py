from typing import List, Optional
from pydantic import BaseModel


class User(BaseModel):
    id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: str


class TelegramGroup(BaseModel):
    id: int
    title: str
    member_count: int = 0  # Default to 0 if None
    description: Optional[str] = None
    username: Optional[str] = None
    is_channel: bool = False
    is_monitored: Optional[bool] = False

    class Config:
        validate_assignment = True


class SendCodeRequest(BaseModel):
    phone_number: str


class CodeVerification(BaseModel):
    phone_number: str
    code: str
    phone_code_hash: str


class AuthResponse(BaseModel):
    message: str
    success: bool
    data: Optional[dict] = None


class GroupsResponse(BaseModel):
    groups: List[TelegramGroup]


class SelectedGroupsRequest(BaseModel):
    group_ids: List[int]
