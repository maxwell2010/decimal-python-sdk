from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from base64 import b64encode, b64decode
from typing import Optional
import os


class Encryption:
    """Класс для шифрования и дешифрования seed-фразы."""

    def __init__(self, key: str):
        """Инициализация шифрования с использованием ключа.

        Args:
            key (str): Ключ шифрования из .env.
        """
        self.fernet = Fernet(self._derive_key(key))

    @staticmethod
    def _derive_key(password: str) -> bytes:
        """Производит ключ шифрования из пароля с использованием PBKDF2.

        Args:
            password (str): Пароль для генерации ключа.

        Returns:
            bytes: Сгенерированный ключ для Fernet.
        """
        salt = b'decimal_sdk_salt'
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = b64encode(kdf.derive(password.encode()))
        return key

    def encrypt(self, data: str) -> str:
        """Шифрует строку (например, seed-фразу).

        Args:
            data (str): Данные для шифрования.

        Returns:
            str: Зашифрованная строка.
        """
        return self.fernet.encrypt(data.encode()).decode()

    def decrypt(self, encrypted_data: str) -> str:
        """Дешифрует зашифрованную строку.

        Args:
            encrypted_data (str): Зашифрованные данные.

        Returns:
            str: Расшифрованная строка.

        Raises:
            ValueError: Если расшифровка не удалась.
        """
        try:
            return self.fernet.decrypt(encrypted_data.encode()).decode()
        except Exception as e:
            raise ValueError(f"Ошибка дешифрования: {e}")

    @staticmethod
    def generate_key() -> str:
        """Генерирует новый ключ шифрования.

        Returns:
            str: Сгенерированный ключ.
        """
        return Fernet.generate_key().decode()