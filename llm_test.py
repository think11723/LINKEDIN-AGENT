from services.llm import LLMFactory

print("Creating provider...")

llm = LLMFactory.get("writer")

print("Provider created!")

response = llm.generate_text(
    "Write one sentence explaining what LangGraph is."
)

print("\nResponse:")
print(response.text)
print("\nModel:", response.model)
print("Latency:", response.latency)