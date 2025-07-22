import os
from dotenv import load_dotenv
from pathlib import Path
from typing import Optional


class Config:
    """Конфигурация для Decimal SDK."""

    def __init__(self, env_path: str = ".env"):
        """Инициализация конфигурации из .env файла.

        Args:
            env_path (str): Путь к .env файлу. По умолчанию '.env'.
        """
        load_dotenv(dotenv_path=Path(env_path))
        self.encryption_key: Optional[str] = os.getenv("ENCRYPTION_KEY")
        self.socket_path: str = os.getenv("SOCKET_PATH", "/tmp/decimal_ipc.sock")

        if not self.encryption_key:
            raise ValueError("ENCRYPTION_KEY не указан в .env файле")

    def get_socket_path(self) -> str:
        """Получить путь к Unix-сокету.

        Returns:
            str: Путь к сокету.
        """
        return self.socket_path

    def get_encryption_key(self) -> str:
        """Получить ключ шифрования.

        Returns:
            str: Ключ шифрования.
        """
        return self.encryption_key
