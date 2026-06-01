"""Application configuration using pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Google Gemini
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-pro"

    # Embeddings — multilingual model for Arabic + English support
    EMBEDDING_MODEL: str = "paraphrase-multilingual-MiniLM-L12-v2"

    # RAG Pipeline Settings
    RAG_TOP_K: int = 15
    RAG_MAX_CONTEXT_CHARS: int = 32000  # ~8000 tokens × 4 chars/token
    RAG_MMR_LAMBDA: float = 0.7
    RAG_HYBRID_ALPHA: float = 0.6  # Weight for semantic vs keyword (0.6 = 60% semantic)

    # LLM Quality Settings
    LLM_TEMPERATURE: float = 0.35
    LLM_MAX_CONTEXT_CHARS: int = 32000  # ~8000 tokens × 4 chars/token

    # Page Budget Settings
    EXERCISES_PER_PAGE_AVG: int = 4

    # Answer correctness verification. Per-subject dispatch is handled by
    # SubjectStrategy.verifier() — math returns MathVerifier, others
    # return None so we never run a math-equation check on prose answers.
    # This setting is the global kill-switch only.
    ANSWER_VERIFICATION_ENABLED: bool = True
    ANSWER_VERIFICATION_TEMPERATURE: float = 0.0
    # Backwards-compat aliases for the pre-Phase-2 setting names. Read
    # via the verification_enabled property so old .env files keep working.
    MATH_VERIFICATION_ENABLED: bool = True
    MATH_VERIFICATION_TEMPERATURE: float = 0.0

    # Exercises per page by density level (single source of truth)
    DENSITY_EXERCISES_PER_PAGE: dict = {
        "spacious": 2,
        "standard": 3,
        "dense": 5,
    }

    # Page weight per exercise type (how much page space each type consumes)
    # 1.0 = one full "slot", <1.0 = compact, >1.0 = takes more space
    EXERCISE_TYPE_PAGE_WEIGHT: dict = {
        "multiple_choice": 1.0,
        "fill_in_blank": 0.7,
        "long_answer": 1.5,
        "true_false": 0.6,
        "show_work": 1.5,
        "matching": 1.2,
    }

    # Database
    DB_PATH: str = "./data/mathcraft.db"

    # File storage
    UPLOAD_DIR: str = "./data/uploads"
    OUTPUT_DIR: str = "./data/workbooks"
    FAISS_DIR: str = "./data/faiss_indices"

    # Limits
    MAX_PDF_SIZE_MB: int = 50

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS_ORIGINS string into a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def verification_enabled(self) -> bool:
        """Single source of truth for whether answer verification runs.

        Honors the new ANSWER_VERIFICATION_ENABLED name AND the legacy
        MATH_VERIFICATION_ENABLED alias so existing .env files keep
        working unchanged. AND-combined: if either is disabled, skip.
        """
        return bool(self.ANSWER_VERIFICATION_ENABLED) and bool(
            self.MATH_VERIFICATION_ENABLED
        )


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings instance."""
    return Settings()
