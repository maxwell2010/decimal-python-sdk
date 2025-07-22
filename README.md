Decimal Python SDK
Python SDK для взаимодействия с блокчейном Decimal через IPC-сервер. Поддерживает создание кошельков, отправку DEL, делегирование валидаторам, создание токенов, выпуск NFT, мультисиг-транзакции, операции с мостом, чеками, IPFS и многое другое с безопасной обработкой seed-фраз с использованием шифрования.
Возможности

Безопасная обработка seed-фраз: Шифрование seed-фраз с использованием Fernet (AES-128 в режиме CBC) с ключом из .env.
Коммуникация через IPC: Взаимодействие с JavaScript-based IPC-сервером для операций с блокчейном.
Полная поддержка dsc-js-sdk: Реализованы все методы из dsc-js-sdk, включая управление кошельками, транзакции, токены, NFT, делегирование, валидаторы, мультисиг, мост, чеки и IPFS.
Идентификация кошелька: Вместо WALLET_ID используется адрес кошелька (в формате 0x1...), полученный из seed-фразы при создании кошелька. Это устраняет необходимость задавать отдельный идентификатор в .env.
Аннотации типов: Полные аннотации типов для лучшей читаемости кода и поддержки IDE.
Модульный дизайн: Легко расширяемый для новых функций при обновлении dsc-js-sdk.
Обработка ошибок: Пользовательские исключения (DecimalSDKError, IPCConnectionError, TransactionError, WalletRegistrationError, ValidationError, IPCError, EncryptionError) для надежного управления ошибками.

Установка

Клонируйте репозиторий:
git clone https://github.com/yourusername/decimal-python-sdk.git
cd decimal-python-sdk


Установите зависимости Python:
pip install -r requirements.txt


Установите зависимости Node.js для IPC-сервера, включая dsc-js-sdk, в корне проекта:
npm install fernet dotenv bip39 dsc-js-sdk

Примечание: dsc-js-sdk устанавливается в папку decimal-python-sdk/node_modules/dsc-js-sdk. Убедитесь, что Node.js и npm установлены.

Создайте файл .env в корне проекта:
ENCRYPTION_KEY=your_secure_key_here
SOCKET_PATH=/tmp/decimal_ipc.sock


ENCRYPTION_KEY: Безопасный ключ для шифрования seed-фраз (32 байта, base64). Сгенерируйте его с помощью:from decimal_sdk import Encryption
print(Encryption.generate_key())


SOCKET_PATH: Путь к Unix-сокету для IPC (по умолчанию /tmp/decimal_ipc.sock).


Убедитесь, что структура проекта включает модуль decimal_sdk/exceptions.py для обработки ошибок:
decimal-python-sdk/
├── decimal_sdk/
│   ├── __init__.py
│   ├── client.py
│   ├── config.py
│   ├── encryption.py
│   ├── exceptions.py
├── ipc-server.js
├── node_modules/
│   ├── dsc-js-sdk/
├── requirements.txt
├── .env
├── README.md


Запустите IPC-сервер:
node ipc-server.js



Использование
Инициализация SDK
from decimal_sdk import DecimalSDK
from decimal_sdk.exceptions import DecimalSDKError, IPCConnectionError, TransactionError, WalletRegistrationError, ValidationError, IPCError, EncryptionError
import asyncio

async def main():
    sdk = DecimalSDK()
    
    try:
        # Создание кошелька
        mnemonic = "word1 word2 ... word12"
        wallet_info = await sdk.create_wallet(mnemonic)
        print(f"Кошелёк создан: {wallet_info['address']}")  # Адрес в формате 0x1...
        
        # Получение баланса
        address = wallet_info['address']
        balance = await sdk.get_balance(address)
        print(f"Баланс: {balance['balance']} DEL")
        
        # Отправка DEL
        success, tx_hash = await sdk.send_del("0x1234567890abcdef1234567890abcdef12345678", 10.5)
        if success:
            print(f"Транзакция: https://explorer.decimalchain.com/transactions/{tx_hash}")
        
        # Делегирование DEL
        success, tx_hash, total = await sdk.delegate_del("0xabcdef1234567890abcdef1234567890abcdef12", 100.0, 0)
        if success:
            print(f"Делегирование: https://explorer.decimalchain.com/transactions/{tx_hash}, Итого: {total} DEL")
        
        # Создание токена
        token = await sdk.create_token(
            symbol="TKNE",
            name="TokenName",
            crr=50,
            initial_mint=1000.0,
            min_total_supply=1.0,
            max_total_supply=5000000.0,
            identity="7815696ecbf1c96e6894b779456d330e"
        )
        print(f"Токен создан: {token}")
    
    except IPCConnectionError as e:
        print(f"Ошибка подключения к IPC: {e}")
    except TransactionError as e:
        print(f"Ошибка транзакции: {e}")
    except WalletRegistrationError as e:
        print(f"Ошибка регистрации кошелька: {e}")
    except ValidationError as e:
        print(f"Ошибка валидации: {e}")
    except IPCError as e:
        print(f"Ошибка IPC: {e}")
    except EncryptionError as e:
        print(f"Ошибка шифрования: {e}")
    except DecimalSDKError as e:
        print(f"Общая ошибка SDK: {e}")

asyncio.run(main())

Доступные методы

Управление кошельками:
create_wallet(mnemonic: str) -> Dict[str, Any]: Создает кошелек с зашифрованной seed-фразой. Возвращает адрес в формате 0x1..., который используется для идентификации кошелька.
is_wallet_registered() -> Dict[str, Any]: Проверяет, зарегистрирован ли кошелек.


Операции с DEL:
send_del(to: str, amount: float) -> Tuple[bool, Optional[str]]: Отправляет DEL на адрес в формате 0x1....
burn_del(amount: float) -> Dict[str, Any]: Сжигает DEL.


Операции с токенами:
create_token(symbol: str, name: str, crr: int, initial_mint: float, min_total_supply: float, max_total_supply: float, identity: str) -> Dict[str, Any]: Создает токен с резервом.
create_token_reserveless(name: str, symbol: str, mintable: bool, burnable: bool, initial_mint: float, cap: Optional[float], identity: str) -> Dict[str, Any]: Создает токен без резерва.
convert_to_del(token_address: str, amount: float, estimate_gas: float, gas_center_address: str, sign: Optional[str]) -> Dict[str, Any]: Конвертирует токены в DEL.
approve_token(token_address: str, spender: str, amount: float) -> Dict[str, Any]: Разрешает spender тратить токены.
transfer_token(token_address: str, to: str, amount: float) -> Dict[str, Any]: Переводит токены на адрес.
И другие методы для операций с токенами (см. client.py).


Операции с NFT:
create_nft_collection(symbol: str, name: str, contract_uri: str, refundable: bool, allow_mint: bool, reserveless: bool, type: str) -> Dict[str, Any]: Создает коллекцию NFT (DRC721/DRC1155).
mint_nft(nft_collection_address: str, to: str, token_uri: str, ...) -> Dict[str, Any]: Минтит NFT.
И другие методы для операций с NFT.


Делегирование:
delegate_del(validator: str, amount: float, days: int) -> Tuple[bool, Optional[str], Optional[float]]: Делегирует DEL валидатору.
delegate_token(validator: str, token_address: str, amount: float, days: int, sign: Optional[str]) -> Dict[str, Any]: Делегирует токены.
И другие методы для управления стейками.


Валидаторы:
add_validator_with_del(reward_address: str, description: Dict[str, str], commission: str, amount: float) -> Dict[str, Any]: Добавляет валидатора с DEL.
add_validator_with_token(reward_address: str, description: Dict[str, str], commission: str, token_address: str, amount: float, sign: Optional[str]) -> Dict[str, Any]: Добавляет валидатора с токеном.
И другие методы для управления валидаторами.


Мультисиг:
create_multisig(owner_data: List[Dict[str, Any]], weight_threshold: int) -> Dict[str, Any]: Создает мультисиг кошелек.
build_tx_send_del(multisig_address: str, to: str, amount: float) -> Dict[str, Any]: Создает транзакцию для отправки DEL.
И другие методы для мультисиг-операций.


Мост:
bridge_transfer_native(to: str, amount: float, from_chain_id: int, to_chain_id: int) -> Dict[str, Any]: Переводит DEL/ETH/BNB через мост.
bridge_transfer_tokens(token_address: str, to: str, amount: float, from_chain_id: int, to_chain_id: int) -> Dict[str, Any]: Переводит токены через мост.


Чеки:
create_checks_del(passwords: List[str], amount: float, block_offset: int) -> Dict[str, Any]: Создает чеки для DEL.
create_checks_token(passwords: List[str], amount: float, block_offset: int, token_address: str, sign: Optional[str]) -> Dict[str, Any]: Создает чеки для токенов.


Просмотр данных:
get_balance(address: str) -> Dict[str, Any]: Получает баланс DEL.
get_balance_eth(address: str) -> Dict[str, Any]: Получает баланс ETH.
get_balance_bnb(address: str) -> Dict[str, Any]: Получает баланс BNB.
И другие методы для получения данных (см. client.py).



Полный список методов см. в client.py.
Обработка ошибок
SDK использует следующие пользовательские исключения, определенные в decimal_sdk/exceptions.py:

DecimalSDKError: Базовое исключение для всех ошибок SDK.
IPCConnectionError: Для ошибок подключения к IPC-серверу (например, недоступность сокета).
TransactionError: Для ошибок выполнения транзакций (например, недостаточно средств).
WalletRegistrationError: Для ошибок регистрации кошелька (например, неверная мнемоника).
ValidationError: Для ошибок валидации входных данных (например, неверный формат адреса).
IPCError: Для общих ошибок взаимодействия с IPC-сервером.
EncryptionError: Для ошибок шифрования/дешифрования seed-фраз.

Замечания

Убедитесь, что IPC-сервер (ipc-server.js) запущен перед использованием SDK.
Все адреса должны быть в EVM-формате (0x1...), так как формат dx2... устарел.
Адрес кошелька, полученный при создании кошелька, автоматически используется для идентификации в запросах. Вызов create_wallet обязателен перед другими операциями.
Для продвинутых операций (например, мультисиг или мост) убедитесь, что у вас есть правильные параметры, такие как chain_id или sign.

Лицензия
MIT License
