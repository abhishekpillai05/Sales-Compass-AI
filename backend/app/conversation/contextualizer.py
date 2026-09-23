"""
Contextual Query Reformulation for Follow-up Questions.

When a user asks a follow-up question such as:
"What are its main features?"
the contextualizer inspects recent conversation history and rewrites the query
into a standalone search query suitable for vector search in Qdrant:
"What are the main features of the Karcher BD 43/40?"
"""
import re
from typing import List, Optional

from app.database.models import ConversationMessage
from app.generation.llm import generate_llm_response
from app.logging.config import get_logger

logger = get_logger(__name__)

# Pronoun and reference triggers indicating a follow-up question
FOLLOW_UP_TRIGGERS = {
    "it",
    "its",
    "they",
    "them",
    "their",
    "this",
    "that",
    "these",
    "those",
    "the product",
    "the machine",
    "the equipment",
    "the item",
    "the scrubber",
    "the cleaner",
    "this one",
    "that one",
}


def is_likely_followup(query: str) -> bool:
    """Heuristic check to detect whether a question contains anaphoric references."""
    q_lower = query.lower()
    tokens = set(re.findall(r"\b\w+\b", q_lower))

    # Check for direct word matches (e.g. "it", "its")
    if tokens & {"it", "its", "they", "them", "their", "this", "these", "those"}:
        return True

    # Check for multi-word phrases
    for phrase in ("the product", "the machine", "the equipment", "this one", "that one"):
        if phrase in q_lower:
            return True

    return False


def contextualize_query(
    query: str,
    history: List[ConversationMessage],
) -> str:
    """
    Contextualize the user's question using recent conversation history.

    Returns a standalone query optimized for vector search.
    Preserves original query if no history exists or if it's already standalone.
    """
    trimmed_query = query.strip()
    if not history or not trimmed_query:
        return trimmed_query

    # Format history turns (last 4 messages for precision)
    recent_history = history[-4:]
    formatted_history = []
    for msg in recent_history:
        role_label = "User" if msg.role == "user" else "Assistant"
        # Truncate very long assistant answers to keep prompt concise
        clean_content = msg.content.strip()
        if len(clean_content) > 300:
            clean_content = clean_content[:300] + "..."
        formatted_history.append(f"{role_label}: {clean_content}")

    history_str = "\n".join(formatted_history)

    # Attempt LLM query rewriting via Groq
    try:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a search query reformulation assistant for a product catalog search engine.\n"
                    "Your task: Given the conversation history and the user's latest question, determine if "
                    "the question is a follow-up that refers to previously mentioned products, entities, or context.\n\n"
                    "Rules:\n"
                    "1. If the question is a follow-up (e.g., uses pronouns like 'it', 'its', 'this product', 'the machine'), "
                    "rewrite it into a single, complete, standalone question that includes the specific product names, "
                    "models, or SKUs from the history.\n"
                    "2. If the question is already complete and standalone, return the original question unchanged.\n"
                    "3. Output ONLY the standalone search query. Do not include quotes, preamble, notes, or explanations."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Conversation History:\n{history_str}\n\n"
                    f"Latest User Question:\n{trimmed_query}\n\n"
                    "Standalone Search Query:"
                ),
            },
        ]

        rewritten = generate_llm_response(messages=messages, temperature=0.0)

        # Clean reasoning tags if any
        rewritten = re.sub(r"<think>.*?</think>", "", rewritten, flags=re.DOTALL).strip()
        rewritten = rewritten.strip('"`\'\n ')

        if rewritten and len(rewritten) > 3:
            logger.info(
                "contextualize_query success original='%s' rewritten='%s'",
                trimmed_query,
                rewritten,
            )
            return rewritten

    except Exception as exc:
        logger.warning(
            "contextualize_query LLM rewrite failed: %s. Using heuristic fallback.",
            exc,
        )

    # Heuristic fallback if LLM rewrite was unavailable or failed
    if is_likely_followup(trimmed_query):
        # Look for the last user question or assistant subject
        for msg in reversed(recent_history):
            if msg.role == "user" and msg.content.strip() != trimmed_query:
                logger.info(
                    "contextualize_query fallback using prior user query='%s'",
                    msg.content.strip(),
                )
                return f"{trimmed_query} (context: {msg.content.strip()})"

    return trimmed_query
