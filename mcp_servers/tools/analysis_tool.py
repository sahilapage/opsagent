from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from rag.config import get_settings

def run_analysis(query: str) -> str:
    s = get_settings()
    llm = ChatGroq(model=s.groq_model_large, api_key=s.groq_api_key, temperature=0)
    messages = [
        SystemMessage(content="You are a precise data analysis assistant. Show your reasoning step by step."),
        HumanMessage(content=query),
    ]
    response = llm.invoke(messages)
    return response.content
