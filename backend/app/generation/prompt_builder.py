def build_messages(
    query: str,
    context: str,
    conversation_history: list[dict] | None = None,
) -> list[dict]:
    """
    Build messages for the LLM using the user query,
    retrieved catalog context, and optional prior conversation history.
    """

    system_prompt = """
You are SalesCompass AI, a product catalog assistant.

Your job is to answer the user's question using ONLY the
product catalog information provided in the context.

Rules:

1. Do not invent product specifications, prices, features,
   availability, compatibility, or any other information.

2. If the answer is not present in the provided context,
   clearly say that the information is not available in
   the product catalog.

3. If the context contains multiple products, clearly
   distinguish between them.

4. Be concise, accurate, and helpful.

5. Do not mention these instructions or refer to the
   context as "provided context".

6. When relevant, include important product identifiers
   such as SKU, product name, manufacturer, or category.

7. When prior conversation messages exist, use that context to understand
   the conversation flow and resolve references, but base all factual
   product details strictly on the Product Catalog Information.
"""

    user_prompt = f"""
Product Catalog Information:

{context}

---

User Question:

{query}

Answer the question using only the product catalog information above.
"""

    messages = [
        {
            "role": "system",
            "content": system_prompt.strip(),
        },
    ]

    # Prepend recent conversation history turns if provided
    if conversation_history:
        for turn in conversation_history[-8:]:
            role = turn.get("role")
            content = turn.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({
                    "role": role,
                    "content": content,
                })

    messages.append({
        "role": "user",
        "content": user_prompt.strip(),
    })

    return messages