class DecimalSDKError(Exception):
    """Базовое исключение для Decimal SDK."""
    pass

class IPCConnectionError(DecimalSDKError):
    """Исключение для ошибок подключения к IPC-серверу."""
    pass

class TransactionError(DecimalSDKError):
    """Исключение для ошибок выполнения транзакций."""
    pass

class WalletRegistrationError(DecimalSDKError):
    """Исключение для ошибок регистрации кошелька."""
    pass

class ValidationError(DecimalSDKError):
    """Исключение для ошибок валидации данных."""
    pass

class IPCError(Exception):
    """Исключение для ошибок, связанных с взаимодействием с IPC-сервером."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class EncryptionError(Exception):
    """Исключение для ошибок, связанных с шифрованием/дешифрованием."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)