from typing import Dict, List, Optional
from app.database.mongodb import db_manager
from app.database.models.conversation import Conversation, ConversationMessage


class ConversationRepository:
    def __init__(self):
        self._conversations: Dict[str, Conversation] = {}
        self._messages: Dict[str, List[ConversationMessage]] = {}

    async def create(self, conversation: Conversation) -> Conversation:
        if db_manager.is_connected:
            await db_manager.db.conversations.insert_one(conversation.model_dump())
        else:
            self._conversations[conversation.id] = conversation
        return conversation

    async def list(self, user_id: str = "anonymous") -> List[Conversation]:
        if db_manager.is_connected:
            return [Conversation(**d) async for d in db_manager.db.conversations.find(
                {"user_id": user_id}).sort("updated_at", -1)]
        return sorted((c for c in self._conversations.values() if c.user_id == user_id),
                      key=lambda c: c.updated_at, reverse=True)

    async def get(self, conversation_id: str) -> Optional[Conversation]:
        if db_manager.is_connected:
            d = await db_manager.db.conversations.find_one({"id": conversation_id})
            return Conversation(**d) if d else None
        return self._conversations.get(conversation_id)

    async def add_message(self, message: ConversationMessage) -> ConversationMessage:
        if db_manager.is_connected:
            await db_manager.db.conversation_messages.insert_one(message.model_dump())
            await db_manager.db.conversations.update_one(
                {"id": message.conversation_id},
                {"$set": {"updated_at": message.created_at},
                 "$addToSet": {"research_ids": {"$each": message.research_ids}}})
        else:
            self._messages.setdefault(message.conversation_id, []).append(message)
            c = self._conversations.get(message.conversation_id)
            if c:
                c.research_ids = list(dict.fromkeys(c.research_ids + message.research_ids))
        return message

    async def list_messages(self, conversation_id: str) -> List[ConversationMessage]:
        if db_manager.is_connected:
            return [ConversationMessage(**d) async for d in db_manager.db.conversation_messages.find(
                {"conversation_id": conversation_id}).sort("created_at", 1)]
        return self._messages.get(conversation_id, [])


conversation_repo = ConversationRepository()
