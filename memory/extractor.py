from __future__ import annotations
import json
import structlog
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from rag.config import get_settings

log = structlog.get_logger()

EXTRACTION_PROMPT = """You are a memory extraction system. Analyze the conversation and extract important facts worth remembering about the user.

Extract ONLY information that is:
- Personal facts (name, location, profession, age)
- Preferences (likes, dislikes, communication style)
- Goals (what they are building, trying to achieve)
- Technical context (tools, languages, frameworks they use)
- Important decisions they made

Return a JSON array of extracted memories. Each memory should be:
- A single clear fact
- Written in third person ("User likes...", "User is building...")
- Concise (under 100 characters)

If nothing worth remembering, return empty array [].

Return ONLY valid JSON array, no explanation.

Examples:
[
  "User's name is Sahil",
  "User is building an AI agent called OpsAgent",
  "User prefers concise answers",
  "User is a computer science student in India"
]"""


def extract_memories(user_message: str, agent_response: str) -> list[str]:
    s = get_settings()
    llm = ChatGroq(model=s.groq_model_fast, api_key=s.groq_api_key, temperature=0)

    conversation = f"User: {user_message}\nAssistant: {agent_response}"

    try:
        response = llm.invoke([
            SystemMessage(content=EXTRACTION_PROMPT),
            HumanMessage(content=conversation),
        ])
        raw = response.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()
        memories = json.loads(raw)
        if isinstance(memories, list):
            log.info("memories_extracted", count=len(memories))
            return [m for m in memories if isinstance(m, str) and len(m) > 5]
        return []
    except Exception as e:
        log.error("extraction_error", error=str(e))
        return []
