# Decimal Python SDK 🧩

**Decimal Python SDK** — это мощная библиотека для взаимодействия с блокчейн-платформой **Decimal** через IPC-сервер. Она предоставляет разработчикам инструменты для создания кошельков, управления токенами, NFT, валидаторами, мультисиг-транзакциями, а также операциями с мостами, чеками и IPFS. 🎉

С безопасной обработкой seed-фраз и полной поддержкой `dsc-js-sdk`, этот SDK идеально подходит для создания приложений на блокчейне Decimal! 🚀

---

## 📖 Возможности

- 🔒 **Безопасная обработка seed-фраз**: Шифрование мнемоник с использованием **Fernet (AES-128 в режиме CBC)** и ключа из `.env`.
- 📡 **Коммуникация через IPC**: Взаимодействие с JavaScript-based IPC-сервером для выполнения операций в блокчейне.
- 🛠️ **Полная поддержка dsc-js-sdk**: Реализованы все методы для работы с кошельками, транзакциями, токенами, NFT, делегированием, валидаторами, мультисиг, мостами, чеками и IPFS.
- 🏦 **Идентификация кошелька**: Используется адрес кошелька (в формате `0x...`) вместо `WALLET_ID`, что устраняет необходимость в дополнительной настройке.
- 📝 **Аннотации типов**: Полные аннотации типов для улучшения читаемости кода и поддержки IDE.
- 🧱 **Модульный дизайн**: Легко расширяемый для новых функций при обновлении `dsc-js-sdk`.
- 🚨 **Обработка ошибок**: Пользовательские исключения для надежного управления ошибками:
  - `DecimalSDKError`
  - `IPCConnectionError`
  - `TransactionError`
  - `WalletRegistrationError`
  - `ValidationError`
  - `IPCError`
  - `EncryptionError`

---

## 📋 Требования

- **Python**: 3.8+ 🐍
- **Node.js**: 14.x или выше 🌐 (16.x рекомендуется для лучшей совместимости)
- **npm**: 6.x или выше
- **Зависимости Python** (указаны в `requirements.txt`):
  - `aiohttp` 📡
  - `python-dotenv` 📜
- **Зависимости Node.js** (устанавливаются в `dsc-js-sdk`):
  - `fernet@0.3.3`
  - `dotenv@17.2.0`
  - `base64-js@1.5.1`
  - `bip39@3.1.0`
  - `dsc-js-sdk@2.0.12`
- **Windows**: Для поддержки IPC-сокета (`\\.\pipe\decimal_ipc`)

---

## 🛠️ Установка

### 1. Клонируйте репозиторий
```bash
git clone https://github.com/maxwell2010/decimal-python-sdk.git
cd decimal-python-sdk
```

### 2. Создайте виртуальное окружение
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
.\.venv\Scripts\activate   # Windows
```

### 3. Установите зависимости Python
```bash
pip install -r requirements.txt
```

### 4. Установите зависимости Node.js и `dsc-js-sdk` 📦
1. **Клонируйте репозиторий `dsc-js-sdk`**:
   ```bash
   git clone https://bitbucket.org/decimalteam/dsc-js-sdk.git
   cd dsc-js-sdk
   npm install
   npm install fernet@0.3.3 dotenv@17.2.0 base64-js@1.5.1 bip39@3.1.0
   npm link
   cd ..
   ```

2. **Свяжите `dsc-js-sdk` с проектом**:
   - **Для Linux/macOS**:
     ```bash
     npm link dsc-js-sdk
     ```
   - **Для Windows**:
     ```powershell
     cd C:\Users\Maximus\PycharmProjects\decimal_python_sdk
     npm link dsc-js-sdk
     ```

   > **Примечание**: Команда `npm link dsc-js-sdk` создаёт папку `node_modules` и файл `package-lock.json` в корне проекта, которые могут содержать дополнительные зависимости. Это не влияет на работу, так как `ipc-server.js` и `test-fernet.js` используют зависимости из `dsc-js-sdk\node_modules`. Чтобы минимизировать корневой `node_modules`, выполните:
   ```powershell
   Remove-Item -Recurse -Force node_modules
   Remove-Item -Force package-lock.json
   npm link dsc-js-sdk
   ```

### 5. Настройте файл `.env`
Создайте файл `.env` в корне проекта с следующим содержимым:
```env
ENCRYPTION_KEY=j7EvB26yrHyIfHTeI523_zx61YFxsPoJdxru51kXo5s=
SOCKET_PATH=\\.\pipe\decimal_ipc
```
- **ENCRYPTION_KEY**: Безопасный ключ (32 байта, base64) для шифрования seed-фраз. Используйте предоставленный ключ или сгенерируйте новый:
  ```python
  from decimal_sdk import Encryption
  print(Encryption.generate_key())
  ```
- **SOCKET_PATH**: Путь к IPC-сокету. Для Windows используйте `\\.\pipe\decimal_ipc`. Для Linux/macOS используйте, например, `/tmp/decimal_ipc.sock`.

### 6. Проверьте структуру проекта
Убедитесь, что структура проекта соответствует следующей:
```
decimal-python-sdk/
├── decimal_sdk/
│   ├── __init__.py
│   ├── client.py
│   ├── config.py
│   ├── encryption.py
│   ├── exceptions.py
├── dsc-js-sdk/
│   ├── node_modules/
│   │   ├── fernet@0.3.3
│   │   ├── dotenv@17.2.0
│   │   ├── base64-js@1.5.1
│   │   ├── bip39@3.1.0
│   │   ├── ... (other dependencies)
│   ├── package.json
│   ├── index.js
├── ipc-server.js
├── test-fernet.js
├── requirements.txt
├── .env
├── README.md
├── node_modules/ (may contain dependencies, but only dsc-js-sdk link is required)
├── package-lock.json (optional, created by npm)
```

### 7. Проверьте работу `test-fernet.js`
```bash
node test-fernet.js
```
Ожидаемый вывод:
```
[dotenv@17.2.0] injecting env (2) from .env (tip: ⚙️  enable debug logging with { debug: true })
ENCRYPTION_KEY действителен для Fernet
```

### 8. Запустите IPC-сервер
```bash
node ipc-server.js
```
Ожидаемый вывод:
```
[dotenv@17.2.0] injecting env (2) from .env (tip: 🔐 prevent building .env in docker: https://dotenvx.com/prebuild)
⚙️ IPC-сервер запущен по пути: \\.\pipe\decimal_ipc
```
> **Примечание**: Сервер должен быть запущен перед использованием SDK.

### 9. Установите SDK как пакет (опционально) 📦
Чтобы использовать `decimal-python-sdk` как библиотеку в других Python-проектах или импортировать `decimal_sdk` из любого места, установите SDK как пакет в режиме разработки:
```bash
pip install -e .
```
> **Примечание**: 
> - Эта команда устанавливает SDK как Python-пакет, ссылаясь на текущую директорию (`decimal-python-sdk`). После этого вы можете импортировать `decimal_sdk` в любом Python-скрипте, например, `from decimal_sdk import DecimalSDK`.
> - Режим `-e` (editable) позволяет вносить изменения в код SDK, и они сразу отражаются без переустановки.
> - Для работы команды требуется файл `setup.py` или `pyproject.toml` в корне проекта. Если он отсутствует, создайте его или обратитесь за помощью.

---

## 🧪 Пример использования

Ниже приведен пример инициализации SDK, создания кошелька, проверки баланса, отправки DEL, делегирования и создания токена:

```python
import asyncio
from decimal_sdk import DecimalSDK
from decimal_sdk.exceptions import DecimalSDKError, IPCConnectionError, TransactionError, WalletRegistrationError, ValidationError, IPCError, EncryptionError

async def main():
    sdk = DecimalSDK()
    
    try:
        # 📌 Создание кошелька
        mnemonic = "word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 word12"
        wallet_info = await sdk.create_wallet(mnemonic)
        print(f"Кошелёк создан: {wallet_info['address']}")  # Адрес в формате 0x...

        # 💰 Получение баланса
        address = wallet_info['address']
        balance = await sdk.get_balance(address)
        print(f"Баланс: {balance['balance']} DEL")

        # 💸 Отправка DEL
        success, tx_hash = await sdk.send_del("0x1234567890abcdef1234567890abcdef12345678", 10.5)
        if success:
            print(f"Транзакция: https://explorer.decimalchain.com/transactions/{tx_hash}")

        # ⚖️ Делегирование DEL
        success, tx_hash, total = await sdk.delegate_del("0xabcdef1234567890abcdef1234567890abcdef12", 100.0, 0)
        if success:
            print(f"Делегирование: https://explorer.decimalchain.com/transactions/{tx_hash}, Итого: {total} DEL")

        # 🪙 Создание токена
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
        print(f"🚨 Ошибка подключения к IPC: {e}")
    except TransactionError as e:
        print(f"🚨 Ошибка транзакции: {e}")
    except WalletRegistrationError as e:
        print(f"🚨 Ошибка регистрации кошелька: {e}")
    except ValidationError as e:
        print(f"🚨 Ошибка валидации: {e}")
    except IPCError as e:
        print(f"🚨 Ошибка IPC: {e}")
    except EncryptionError as e:
        print(f"🚨 Ошибка шифрования: {e}")
    except DecimalSDKError as e:
        print(f"🚨 Общая ошибка SDK: {e}")

asyncio.run(main())
```

---

## 📚 Документация

### Основные методы

#### 🏦 Управление кошельками
- `create_wallet(mnemonic: str) -> Dict[str, Any]`: Создает кошелек с зашифрованной seed-фразой. Возвращает адрес в формате `0x...`.
- `is_wallet_registered() -> Dict[str, Any]`: Проверяет, зарегистрирован ли кошелек.

#### 💸 Операции с DEL
- `send_del(to: str, amount: float) -> Tuple[bool, Optional[str]]`: Отправляет DEL на указанный адрес.
- `burn_del(amount: float) -> Dict[str, Any]`: Сжигает указанное количество DEL.

#### 🪙 Операции с токенами
- `create_token(symbol: str, name: str, crr: int, initial_mint: float, min_total_supply: float, max_total_supply: float, identity: str) -> Dict[str, Any]`: Создает токен с резервом.
- `create_token_reserveless(name: str, symbol: str, mintable: bool, burnable: bool, initial_mint: float, cap: Optional[float], identity: str) -> Dict[str, Any]`: Создает токен без резерва.
- `convert_to_del(token_address: str, amount: float, estimate_gas: float, gas_center_address: str, sign: Optional[str]) -> Dict[str, Any]`: Конвертирует токены в DEL.
- `approve_token(token_address: str, spender: str, amount: float) -> Dict[str, Any]`: Разрешает spender тратить токены.
- `transfer_token(token_address: str, to: str, amount: float) -> Dict[str, Any]`: Переводит токены на адрес.

#### 🖼️ Операции с NFT
- `create_nft_collection(symbol: str, name: str, contract_uri: str, refundable: bool, allow_mint: bool, reserveless: bool, type: str) -> Dict[str, Any]`: Создает коллекцию NFT (DRC721/DRC1155).
- `mint_nft(nft_collection_address: str, to: str, token_uri: str, ...) -> Dict[str, Any]`: Минтит NFT.

#### ⚖️ Делегирование
- `delegate_del(validator: str, amount: float, days: int) -> Tuple[bool, Optional[str], Optional[float]]`: Делегирует DEL валидатору.
- `delegate_token(validator: str, token_address: str, amount: float, days: int, sign: Optional[str]) -> Dict[str, Any]`: Делегирует токены.

#### 🛡️ Валидаторы
- `add_validator_with_del(reward_address: str, description: Dict[str, str], commission: str, amount: float) -> Dict[str, Any]`: Добавляет валидатора с DEL.
- `add_validator_with_token(reward_address: str, description: Dict[str, str], commission: str, token_address: str, amount: float, sign: Optional[str]) -> Dict[str, Any]`: Добавляет валидатора с токеном.

#### 🔒 Мультисиг
- `create_multisig(owner_data: List[Dict[str, Any]], weight_threshold: int) -> Dict[str, Any]`: Создает мультисиг кошелек.
- `build_tx_send_del(multisig_address: str, to: str, amount: float) -> Dict[str, Any]`: Создает транзакцию для отправки DEL.

#### 🌉 Мост
- `bridge_transfer_native(to: str, amount: float, from_chain_id: int, to_chain_id: int) -> Dict[str, Any]`: Переводит DEL/ETH/BNB через мост.
- `bridge_transfer_tokens(token_address: str, to: str, amount: float, from_chain_id: int, to_chain_id: int) -> Dict[str, Any]`: Переводит токены через мост.

#### 🧾 Чеки
- `create_checks_del(passwords: List[str], amount: float, block_offset: int) -> Dict[str, Any]`: Создает чеки для DEL.
- `create_checks_token(passwords: List[str], amount: float, block_offset: int, token_address: str, sign: Optional[str]) -> Dict[str, Any]`: Создает чеки для токенов.

#### 📊 Просмотр данных
- `get_balance(address: str) -> Dict[str, Any]`: Получает баланс DEL.
- `get_balance_eth(address: str) -> Dict[str, Any]`: Получает баланс ETH.
- `get_balance_bnb(address: str) -> Dict[str, Any]`: Получает баланс BNB.

> **Полный список методов** см. в `decimal_sdk/client.py`.

---

## 🚨 Обработка ошибок

SDK использует следующие пользовательские исключения, определенные в `decimal_sdk/exceptions.py`:

- 🛑 `DecimalSDKError`: Базовое исключение для всех ошибок SDK.
- 📡 `IPCConnectionError`: Ошибки подключения к IPC-серверу (например, недоступность сокета).
- 💸 `TransactionError`: Ошибки выполнения транзакций (например, недостаточно средств).
- 🏦 `WalletRegistrationError`: Ошибки регистрации кошелька (например, неверная мнемоника).
- ✅ `ValidationError`: Ошибки валидации входных данных (например, неверный формат адреса).
- 🔌 `IPCError`: Общие ошибки взаимодействия с IPC-сервером.
- 🔒 `EncryptionError`: Ошибки шифрования/дешифрования seed-фраз.

---

## 🛠️ Тестирование

Для запуска тестов установите `pytest` и `pytest-asyncio`:
```bash
pip install pytest pytest-asyncio
pytest tests/
```
> **Примечание**: Убедитесь, что `ipc-server.js` запущен перед тестированием.

---

## 🔐 Замечания по безопасности

- Зависимости `dsc-js-sdk` (`axios@0.29.0`, `form-data@2.5.3`, `tough-cookie@4.1.2`, `secp256k1`, `tar`, `ws`) имеют известные уязвимости. Проверьте их с помощью:
  ```bash
  cd dsc-js-sdk
  npm audit
  ```
- Для совместимости с `dsc-js-sdk@2.0.12` текущие версии зависимостей сохранены. Для продакшена рекомендуется обновить зависимости (например, `axios@0.29.1`, `form-data@2.5.4`, `tough-cookie@4.1.3`) и тщательно протестировать:
  ```bash
  cd dsc-js-sdk
  npm install axios@0.29.1 form-data@2.5.4 tough-cookie@4.1.3
  ```

---

## 📝 Замечания

- 🚀 **Запуск IPC-сервера**: Убедитесь, что `ipc-server.js` запущен перед использованием SDK.
- 🔍 **Формат адресов**: Все адреса должны быть в EVM-формате (`0x...`). Формат `dx2...` устарел.
- 🏦 **Создание кошелька**: Вызов `create_wallet` обязателен перед другими операциями, так как адрес кошелька используется для идентификации.
- ⚙️ **Продвинутые операции**: Для мультисиг, мостов и других операций проверяйте правильность параметров (`chain_id`, `sign` и т.д.).
- 📦 **Корневой `node_modules`**: Папка `node_modules` в корне проекта создаётся при выполнении `npm link dsc-js-sdk` и может содержать дополнительные зависимости. Это не влияет на работу, так как зависимости загружаются из `dsc-js-sdk\node_modules`. Для минимизации корневого `node_modules` выполните:
  ```powershell
  Remove-Item -Recurse -Force node_modules
  Remove-Item -Force package-lock.json
  npm link dsc-js-sdk
  ```

---

## 📬 Контакты

- 🌐 **Сайт**: [mintcandy.ru](https://mintcandy.ru)
- 📧 **Поддержка**: [MintCandySupport](https://t.me/MintCandySupportBot)
- 🐛 **GitHub Issues**: [Создать проблему](https://github.com/maxwell2010/decimal-python-sdk/issues)
- 📩 **Telegram**: [@Maxwell2019](https://t.me/Maxwell2019)

---

## 📜 Лицензия

Проект распространяется под лицензией **MIT**. Подробности см. в файле `LICENSE`.

---

⭐ **Понравился проект?** Поставьте звезду на GitHub! 🌟
