from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "opsagent_knowledge"

    # LLM
    groq_api_key: str = ""
    groq_model_large: str = "llama-3.3-70b-versatile"
    groq_model_fast: str = "llama-3.1-8b-instant"

    # Embeddings — upgraded to large model
    embed_model: str = "mixedbread-ai/mxbai-embed-large-v1"
    embed_dim: int = 1024

    # Chunking
    chunk_size: int = 800
    chunk_overlap: int = 150

    # Retrieval
    retrieval_top_k: int = 5
    retrieval_fetch_k: int = 20

    # Postgres
    database_url: str = "postgresql://opsagent:opsagent_secret@localhost:5432/opsagent"

    # Observability
    langchain_api_key: str = ""
    langchain_project: str = "opsagent"

    # Cohere (optional, fallback to local reranker if empty)
    cohere_api_key: str = ""

    #serper web_search_agent
    serper_api_key: str = ""

    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    whisper_model: str = "base"

    github_token: str = ""
    github_default_repo: str = ""

    app_env: str = "development"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
