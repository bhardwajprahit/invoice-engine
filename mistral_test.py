import os

from mistralai.client import Mistral


client = Mistral(
    api_key=os.getenv("MISTRAL_API_KEY")
)

response = client.chat.complete(
    model="ministral-8b-2512",
    messages=[
        {
            "role": "user",
            "content": "Reply with exactly: INVOICE ENGINE READY"
        }
    ]
)

print(response.choices[0].message.content)