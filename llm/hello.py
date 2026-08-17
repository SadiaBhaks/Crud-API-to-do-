"""
Stage 0 throwaway script — proves you can get one word out of a model,
from your own machine, before building anything real on top of it.

Run with:
    python -m llm.hello

Three environment variables are the entire difference between a model
running on your laptop (Ollama) and one running in a datacenter
(OpenRouter): LLM_BASE_URL, LLM_API_KEY, LLM_MODEL. Nothing else in this
file changes. That's why nobody should ever hard-code a provider.
"""

import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    base_url=os.environ["LLM_BASE_URL"],
    api_key=os.environ["LLM_API_KEY"],
    timeout=30.0,
    max_retries=0,
)

if __name__ == "__main__":
    res = client.chat.completions.create(
        model=os.environ["LLM_MODEL"],
        messages=[{"role": "user", "content": "Reply with exactly the word: ready"}],
    )
    print(res.choices[0].message.content)