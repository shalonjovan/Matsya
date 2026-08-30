from pydantic_settings import BaseSettings
class Settings(BaseSettings):
    storage_path: str = "./data/simulations"
    anuga_mock: bool = True
settings = Settings()
