from app.retrieval.retriever import retrieve
from app.generation.context_builder import build_context
from app.generation.prompt_builder import build_messages


response = retrieve(
    query="I need an industrial router",
    top_k=3,
)

context = build_context(response)

messages = build_messages(
    query="What is the SKU and manufacturer of the industrial router?",
    context=context,
)

print("\n" + "=" * 60)
print("SYSTEM MESSAGE")
print("=" * 60)

print(messages[0]["content"])

print("\n" + "=" * 60)
print("USER MESSAGE")
print("=" * 60)

print(messages[1]["content"])