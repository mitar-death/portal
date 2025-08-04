from pydantic import BaseModel
from typing import List, Optional

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

class SendCodeRequest(BaseModel):
    phone_number: str

class CodeVerification(BaseModel):
    phone_number: str
    code: str
    phone_code_hash: str

class AuthResponse(BaseModel):
    user: Optional[User] = None
    message: str
    success: bool
    token: Optional[str] = None

class GroupsResponse(BaseModel):
    groups: List[TelegramGroup]
    
class SelectedGroupsRequest(BaseModel):
    group_ids: List[int]