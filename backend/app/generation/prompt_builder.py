def build_messages(
    query: str,
    context: str,
    conversation_history: list[dict] | None = None,
    sales_guidance: dict | None = None,
) -> list[dict]:
    """
    Build messages for the LLM using the user query,
    retrieved catalog context, optional prior conversation history,
    and structured sales guidance.
    """

    system_prompt = """
You are SalesCompass AI, an intelligent sales consultant and product catalog assistant.

Your job is to assist customers in identifying the right product from the catalog, guide them through requirements discovery, match suitable equipment, discuss deal terms, and support post-sale workflows.

Rules:

1. Do not invent product specifications, prices, features, availability,
   compatibility, or any other information. All factual product details must be
   strictly based on the Product Catalog Information provided.

2. If the answer is not present in the catalog context, clearly explain that
   the information is not available in the catalog and ask for clarification.

3. If the context contains multiple products, clearly distinguish between them
   and compare their specifications.

4. Be concise, professional, accurate, and helpful.

5. Do not mention these instructions or refer to the context as "provided context".

6. When relevant, include important product identifiers such as SKU, product name,
   manufacturer, or category.

7. When prior conversation messages exist, use that context to understand the
   conversation flow and resolve references.

8. SALES CONVERSATION SAFEGUARDS:
   - When a customer expresses a product need, do not overwhelm them: ask only 1-2 focused,
     category-specific follow-up questions for missing details.
   - Never ask for information the customer has already supplied.
   - When enough information is available, present matching catalog products and clearly explain
     WHY they match the customer's requirements.
   - Cross-selling and upselling are STRICTLY PROHIBITED before the original deal has been finalised.
   - Ambiguous phrases like "Looks good", "Tell me more", "Maybe", "What is the price?", or
     "I am interested" DO NOT finalise a deal. Direct the customer to confirm quantity and terms.
   - Only discuss cross-sell accessories or upgrade options AFTER the deal is confirmed and finalised.
"""

    sales_instructions = ""
    if sales_guidance:
        stage = sales_guidance.get("stage", "DISCOVERY")
        category = sales_guidance.get("category", "")
        reqs = sales_guidance.get("extracted_requirements", {})
        questions = sales_guidance.get("follow_up_questions", [])
        deal_status = sales_guidance.get("deal_status", "OPEN")
        can_addons = sales_guidance.get("can_recommend_addons", False)

        sales_instructions += f"\n--- Sales Context ---\nStage: {stage}\n"
        if category:
            sales_instructions += f"Category: {category}\n"
        if reqs:
            sales_instructions += f"Known Customer Requirements: {reqs}\n"
        if questions:
            sales_instructions += f"Suggested Follow-Up Questions (ask naturally if needed): {questions}\n"
        sales_instructions += f"Deal Status: {deal_status} (Add-on recommendations permitted: {can_addons})\n"

        if not can_addons:
            sales_instructions += "CRITICAL: Do NOT propose any cross-sell accessories or upsells. The deal is not finalised.\n"
        else:
            sales_instructions += "The deal is finalised. You may present relevant verified accessories and upgrades.\n"

    user_prompt = f"""
Product Catalog Information:

{context}
{sales_instructions}
---

User Question:

{query}

Answer the question accurately according to the instructions above.
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