from app.retrieval.retriever import retrieve
from app.generation.generator import generate_response


query = "Tell me about a product with SKU XYZ-NOT-FOUND"


retrieval_response = retrieve(
    query=query,
    sku="XYZ-NOT-FOUND",
)


response = generate_response(
    query=query,
    retrieval_response=retrieval_response,
)


print("\nAnswer:")
print(response["answer"])

print("\nSources:")
print(response["sources"])