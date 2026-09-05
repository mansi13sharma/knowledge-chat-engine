from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    database_url: str = "postgresql://postgres:postgres@localhost:5432/tef_chatbot"

    chroma_persist_dir: str = "./chroma_data"

    faq_data_dir: str = "./faq"
    kb_data_dir: str = "./knowledgebase"
    faq_collection_name: str = "faqs"
    kb_collection_name: str = "knowledge_base"

    faq_top_k: int = 3
    kb_top_k: int = 4
    # Cosine distance thresholds (lower = stricter match). Loosened by
    # retry_loosen_factor on the second attempt of each layer.
    faq_distance_threshold: float = 0.35
    kb_distance_threshold: float = 0.45
    retry_loosen_factor: float = 1.4
    max_layer_attempts: int = 2

    confidence_threshold: float = 0.6
    confidence_retrieval_weight: float = 0.4

    # Number of consecutive low-confidence/not-found turns for which we offer
    # follow-up questions instead of escalating. Once this many consecutive
    # unsuccessful turns have occurred, the next unsuccessful turn escalates.
    max_followup_attempts: int = 1

    support_email: str = "support@example.com"
    support_phone: str = "+1-555-0100-000"

    frontend_origin: str = "http://localhost:5173"


settings = Settings()
