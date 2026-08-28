from app.retrieval.retriever import retrieve
from app.generation.context_builder import build_context


response = retrieve(
    query="I need an industrial router",
    top_k=3,
)


context = build_context(response)


print("\n" + "=" * 60)
print("RETRIEVAL CONTEXT")
print("=" * 60)

print(context)