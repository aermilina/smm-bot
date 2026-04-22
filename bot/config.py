from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    BOT_TOKEN: str
    GEMINI_API_KEY: str = ""        # single key — legacy
    GEMINI_API_KEYS: str = ""       # comma-separated list — takes priority
    FREESOUND_API_KEY: str = ""

    class Config:
        env_file = ".env"

    def get_gemini_keys(self) -> list[str]:
        if self.GEMINI_API_KEYS:
            keys = [k.strip() for k in self.GEMINI_API_KEYS.split(",") if k.strip()]
            if keys:
                return keys
        if self.GEMINI_API_KEY:
            return [self.GEMINI_API_KEY]
        raise ValueError("No Gemini API keys configured. Set GEMINI_API_KEY or GEMINI_API_KEYS in .env")


settings = Settings()
