from app.generation.llm import generate_llm_response


messages = [
    {
        "role": "user",
        "content": "Explain what an industrial router is in two sentences."
    }
]


response = generate_llm_response(
    messages
)


print("\nGROQ RESPONSE:")
print(response)