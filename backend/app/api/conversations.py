from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from app.database.models.user import UserInDB
from app.database.models.conversation import Conversation, ConversationCreate, ConversationMessage, MessageCreate
from app.database.repositories.conversation_repo import conversation_repo
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/conversations", tags=["Conversations"])

def _user_id(user: Optional[UserInDB]) -> str:
    return user.id if user else "anonymous"

@router.post("", response_model=Conversation)
async def create_conversation(req: ConversationCreate, user: Optional[UserInDB] = Depends(get_current_user)):
    return await conversation_repo.create(Conversation(user_id=_user_id(user), title=req.title))

@router.get("", response_model=List[Conversation])
async def list_conversations(user: Optional[UserInDB] = Depends(get_current_user)):
    return await conversation_repo.list(_user_id(user))

@router.get("/{conversation_id}/messages", response_model=List[ConversationMessage])
async def list_messages(conversation_id: str):
    if not await conversation_repo.get(conversation_id):
        raise HTTPException(404, "Conversation not found")
    return await conversation_repo.list_messages(conversation_id)

@router.post("/{conversation_id}/messages", response_model=ConversationMessage)
async def post_message(conversation_id: str, req: MessageCreate):
    if not await conversation_repo.get(conversation_id):
        raise HTTPException(404, "Conversation not found")
    return await conversation_repo.add_message(ConversationMessage(
        conversation_id=conversation_id, content=req.content, research_ids=req.research_ids))
