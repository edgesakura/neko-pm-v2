"""
AgentCore Memory integration module (STM + LTM)

This module provides memory operations for the Izakaya Agent using
Amazon Bedrock AgentCore Memory with short-term and long-term memory.
"""
import logging
import os
from typing import List, Dict, Any

from bedrock_agentcore.memory import MemoryClient
from bedrock_agentcore.memory.session import MemorySessionManager

logger = logging.getLogger(__name__)

# Memory ID from environment variable
MEMORY_ID = os.getenv('MEMORY_ID', 'izakaya_agent_mem-ZOMh0R8tfz')
REGION = 'ap-northeast-1'

# Initialize Memory Client (STM)
memory_client = MemoryClient(region_name=REGION)

# Initialize Session Manager (LTM)
session_manager = MemorySessionManager(
    memory_id=MEMORY_ID,
    region_name=REGION,
)


def get_conversation_history(
    actor_id: str,
    session_id: str,
    k: int = 3,
) -> List[Dict[str, Any]]:
    """
    Retrieve past k conversation turns from short-term memory.

    Args:
        actor_id: User identifier (Cognito sub or LINE user_id)
        session_id: Session ID
        k: Number of turns to retrieve

    Returns:
        List of conversation turns
    """
    try:
        turns = memory_client.get_last_k_turns(
            memory_id=MEMORY_ID,
            actor_id=actor_id,
            session_id=session_id,
            k=k
        )
        return turns if turns else []
    except Exception:
        logger.warning("Failed to retrieve conversation history for actor=%s", actor_id)
        return []


def save_conversation(
    actor_id: str,
    session_id: str,
    user_message: str,
    agent_response: str,
) -> bool:
    """
    Save conversation to AgentCore Memory (triggers LTM extraction).

    Args:
        actor_id: User identifier
        session_id: Session ID
        user_message: User's message
        agent_response: Agent's response

    Returns:
        True if saved successfully
    """
    try:
        messages = [
            (user_message, "USER"),
            (agent_response, "ASSISTANT")
        ]

        memory_client.create_event(
            memory_id=MEMORY_ID,
            actor_id=actor_id,
            session_id=session_id,
            messages=messages
        )
        return True
    except Exception:
        logger.warning("Failed to save conversation for actor=%s", actor_id)
        return False


def retrieve_user_preferences(
    actor_id: str,
    session_id: str,
    query: str = "ユーザーの好み ジャンル 予算 エリア 雰囲気",
) -> List[Dict[str, Any]]:
    """
    Retrieve user preferences from long-term memory.

    Uses UserPreferenceStrategy to find stored preferences.

    Args:
        actor_id: User identifier
        session_id: Session ID
        query: Search query for preferences

    Returns:
        List of preference memory records
    """
    try:
        session = session_manager.create_memory_session(
            actor_id=actor_id,
            session_id=session_id,
        )

        memories = session.search_long_term_memories(
            namespace_prefix=f"/users/{actor_id}/preferences/",
            query=query,
            top_k=5,
        )
        return memories if memories else []
    except Exception:
        logger.warning("Failed to retrieve preferences for actor=%s", actor_id)
        return []


def retrieve_dining_facts(
    actor_id: str,
    session_id: str,
    query: str = "お気に入りの店 よく行くエリア 過去の検索",
) -> List[Dict[str, Any]]:
    """
    Retrieve semantic facts from long-term memory.

    Uses SemanticStrategy to find stored facts about dining history.

    Args:
        actor_id: User identifier
        session_id: Session ID
        query: Search query for facts

    Returns:
        List of semantic memory records
    """
    try:
        session = session_manager.create_memory_session(
            actor_id=actor_id,
            session_id=session_id,
        )

        memories = session.search_long_term_memories(
            namespace_prefix=f"/facts/{actor_id}/",
            query=query,
            top_k=5,
        )
        return memories if memories else []
    except Exception:
        logger.warning("Failed to retrieve dining facts for actor=%s", actor_id)
        return []


def search_semantic_memory(
    actor_id: str,
    session_id: str,
    query: str,
) -> List[Dict[str, Any]]:
    """
    Search both preferences and facts from long-term memory.

    Args:
        actor_id: User identifier
        session_id: Session ID
        query: Search query

    Returns:
        Combined list of memory records
    """
    preferences = retrieve_user_preferences(actor_id, session_id, query)
    facts = retrieve_dining_facts(actor_id, session_id, query)
    return preferences + facts
