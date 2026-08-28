def build_messages(
    query: str,
    context: str,
) -> list[dict]:
    """
    Build messages for the LLM using the
    user query and retrieved catalog context.
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
        {
            "role": "user",
            "content": user_prompt.strip(),
        },
    ]

    return messages