import asyncio
import json
import os
from typing import Dict, Any, Optional
import socket
from .exceptions import IPCConnectionError


class IPCClient:
    """Клиент для взаимодействия с IPC-сервером Decimal."""

    def __init__(self, socket_path: str):
        """Инициализация IPC-клиента.

        Args:
            socket_path (str): Путь к Unix-сокету.
        """
        self.socket_path = socket_path

    async def _convert_big_number(self, data: Any) -> Any:
        """Рекурсивно конвертирует BigNumber в float (DEL).

        Args:
            data: Данные для конвертации (словарь, список или примитив).

        Returns:
            Any: Конвертированные данные.
        """
        if isinstance(data, dict):
            if data.get("type") == "BigNumber" and "hex" in data:
                raw_value = int(data["hex"], 16)
                return round(raw_value / (10 ** 18), 6)
            return {key: await self._convert_big_number(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [await self._convert_big_number(item) for item in data]
        return data

    async def send_request(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Отправляет запрос на IPC-сервер и возвращает ответ.

        Args:
            action (str): Действие (например, 'register_wallet', 'send_del').
            payload (Dict[str, Any]): Данные запроса.

        Returns:
            Dict[str, Any]: Ответ сервера.

        Raises:
            IPCConnectionError: Если не удалось подключиться к сокету.
        """
        if not os.path.exists(self.socket_path):
            raise IPCConnectionError(f"Сокет {self.socket_path} не найден. Сервер запущен?")

        try:
            reader, writer = await asyncio.open_unix_connection(self.socket_path)
        except Exception as e:
            raise IPCConnectionError(f"Не удалось подключиться к сокету: {e}")

        try:
            request = {"action": action, "payload": payload}
            writer.write(json.dumps(request).encode())
            await writer.drain()

            response = await reader.read(65536)
            writer.close()
            await writer.wait_closed()

            try:
                result = json.loads(response.decode())
                return await self._convert_big_number(result)
            except json.JSONDecodeError:
                return {"error": "Неверный формат JSON", "raw": response.decode()}
        except Exception as e:
            raise IPCConnectionError(f"Ошибка при выполнении запроса: {e}")