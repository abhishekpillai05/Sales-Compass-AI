from app.retrieval.retriever import retrieve
from app.generation.generator import generate_response


query = "What is the SKU and manufacturer of the industrial router?"


# Step 1: Retrieve relevant chunks
retrieval_response = retrieve(
    query=query,
    top_k=3,
)


# Step 2: Generate final response
response = generate_response(
    query=query,
    retrieval_response=retrieval_response,
)


print("\n" + "=" * 60)
print("FINAL RESPONSE")
print("=" * 60)

print("\nQuery:")
print(response["query"])

print("\nAnswer:")
print(response["answer"])

print("\nSources:")

for source in response["sources"]:
    print(source)