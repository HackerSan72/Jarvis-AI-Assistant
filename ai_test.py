from openai import OpenAI
from pathlib import Path

# Read the API key from your private file
key_path = Path.home() / ".config" / "jarvis" / "api_key.txt"
api_key = key_path.read_text().strip()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key
)

try:
    response = client.chat.completions.create(
        model="openrouter/free",
        messages=[
            {
                "role": "user",
                "content": "Hello! You are helping me build JARVIS. Introduce yourself in one sentence."
            }
        ],
        max_tokens=300
    )

    message = response.choices[0].message

    print("JARVIS AI:", message.content)
    print("Full message:", message.model_dump())
    print("Finish reason:", response.choices[0].finish_reason)
    print("Model used:", response.model)

except Exception as e:
    print("Error:", repr(e))
    print("Underlying cause:", repr(e.__cause__))