import json
import asyncio
from typing import Dict, Any, Optional, List, Tuple
from decimal_sdk.encryption import Encryption
from decimal_sdk.config import Config
from decimal_sdk.exceptions import DecimalSDKError, IPCConnectionError, TransactionError, WalletRegistrationError, \
    ValidationError, IPCError, EncryptionError


class DecimalSDK:
    def __init__(self, socket_path: Optional[str] = None):
        """Инициализация SDK с настройками из .env."""
        self.config = Config()
        self.socket_path = socket_path or self.config.socket_path
        self.encryption = Encryption(self.config.encryption_key)
        self.wallet_address: Optional[str] = None  # Хранит адрес кошелька после создания

    async def _send_request(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Отправляет запрос на IPC-сервер и возвращает ответ."""
        if not self.wallet_address:
            raise WalletRegistrationError("Кошелек не создан. Сначала вызовите create_wallet.")

        payload['wallet_address'] = self.wallet_address
        request = {'action': action, 'payload': payload}

        try:
            reader, writer = await asyncio.open_unix_connection(self.socket_path)
        except (ConnectionError, FileNotFoundError) as e:
            raise IPCConnectionError(f"Ошибка подключения к IPC: {str(e)}")

        try:
            writer.write(json.dumps(request).encode())
            await writer.drain()

            data = await reader.read(4096)
            writer.close()
            await writer.wait_closed()

            response = json.loads(data.decode())
            if not response.get('success'):
                error_msg = response.get('error', 'Неизвестная ошибка')
                if 'transaction' in error_msg.lower():
                    raise TransactionError(f"Ошибка транзакции: {error_msg}")
                elif 'wallet' in error_msg.lower():
                    raise WalletRegistrationError(f"Ошибка регистрации кошелька: {error_msg}")
                elif 'validation' in error_msg.lower():
                    raise ValidationError(f"Ошибка валидации: {error_msg}")
                raise IPCError(f"Ошибка IPC: {error_msg}")
            return response.get('result', {})
        except Exception as e:
            raise IPCError(f"Ошибка при взаимодействии с IPC-сервером: {str(e)}")

    async def create_wallet(self, mnemonic: str) -> Dict[str, Any]:
        """Создает кошелек с зашифрованной мнемоникой."""
        try:
            encrypted_mnemonic = self.encryption.encrypt(mnemonic)
            result = await self._send_request('create_wallet', {
                'mnemonic': encrypted_mnemonic
            })
            self.wallet_address = result.get('address')
            if not self.wallet_address or not self.wallet_address.startswith('0x'):
                raise WalletRegistrationError("Неверный формат адреса кошелька")
            return result
        except EncryptionError as e:
            raise EncryptionError(f"Ошибка шифрования мнемоники: {str(e)}")
        except Exception as e:
            raise WalletRegistrationError(f"Ошибка создания кошелька: {str(e)}")

    async def is_wallet_registered(self) -> Dict[str, Any]:
        """Проверяет, зарегистрирован ли кошелек."""
        return await self._send_request('is_wallet_registered', {})

    async def send_del(self, to: str, amount: float) -> Tuple[bool, Optional[str]]:
        """Отправляет DEL на указанный адрес."""
        if not to.startswith('0x'):
            raise ValidationError("Адрес получателя должен быть в формате 0x...")
        try:
            result = await self._send_request('send_del', {'to': to, 'amount': amount})
            return result.get('success', False), result.get('transactionHash')
        except Exception as e:
            raise TransactionError(f"Ошибка отправки DEL: {str(e)}")

    async def burn_del(self, amount: float) -> Dict[str, Any]:
        """Сжигает указанное количество DEL."""
        if amount <= 0:
            raise ValidationError("Сумма для сжигания должна быть положительной")
        return await self._send_request('burn_del', {'amount': amount})

    async def create_token(self, symbol: str, name: str, crr: int, initial_mint: float,
                           min_total_supply: float, max_total_supply: float, identity: str) -> Dict[str, Any]:
        """Создает токен с резервом."""
        if not (0 <= crr <= 100):
            raise ValidationError("CRR должен быть в диапазоне от 0 до 100")
        if min_total_supply > max_total_supply:
            raise ValidationError("Минимальный объем не может превышать максимальный")
        return await self._send_request('create_token', {
            'symbol': symbol, 'name': name, 'crr': crr, 'initial_mint': initial_mint,
            'min_total_supply': min_total_supply, 'max_total_supply': max_total_supply, 'identity': identity
        })

    async def create_token_reserveless(self, name: str, symbol: str, mintable: bool, burnable: bool,
                                       initial_mint: float, cap: Optional[float] = None, identity: str = '') -> Dict[
        str, Any]:
        """Создает токен без резерва."""
        if initial_mint <= 0:
            raise ValidationError("Начальный объем должен быть положительным")
        return await self._send_request('create_token_reserveless', {
            'name': name, 'symbol': symbol, 'mintable': mintable, 'burnable': burnable,
            'initial_mint': initial_mint, 'cap': cap, 'identity': identity
        })

    async def convert_to_del(self, token_address: str, amount: float, estimate_gas: float,
                             gas_center_address: str, sign: Optional[str] = None) -> Dict[str, Any]:
        """Конвертирует токены в DEL."""
        if not (token_address.startswith('0x') and gas_center_address.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        payload = {'token_address': token_address, 'amount': amount, 'estimate_gas': estimate_gas,
                   'gas_center_address': gas_center_address}
        if sign:
            payload['sign'] = sign
        return await self._send_request('convert_to_del', payload)

    async def approve_token(self, token_address: str, spender: str, amount: float) -> Dict[str, Any]:
        """Разрешает spender тратить токены."""
        if not (token_address.startswith('0x') and spender.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        return await self._send_request('approve_token',
                                        {'token_address': token_address, 'spender': spender, 'amount': amount})

    async def transfer_token(self, token_address: str, to: str, amount: float) -> Dict[str, Any]:
        """Переводит токены на адрес."""
        if not (token_address.startswith('0x') and to.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        return await self._send_request('transfer_token', {'token_address': token_address, 'to': to, 'amount': amount})

    async def transfer_from_token(self, token_address: str, from_address: str, to: str, amount: float) -> Dict[str, Any]:
        """Переводит токены от имени владельца."""
        if not (token_address.startswith('0x') and from_address.startswith('0x') and to.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        return await self._send_request('transfer_from_token', {
            'token_address': token_address, 'from': from_address, 'to': to, 'amount': amount
        })

    async def burn_token(self, token_address: str, amount: float) -> Dict[str, Any]:
        """Сжигает токены."""
        if not token_address.startswith('0x'):
            raise ValidationError("Адрес токена должен быть в формате 0x...")
        if amount <= 0:
            raise ValidationError("Сумма для сжигания должна быть положительной")
        return await self._send_request('burn_token', {'token_address': token_address, 'amount': amount})

    async def buy_token_for_exact_del(self, token_address: str, amount_del: float, recipient: str) -> Dict[str, Any]:
        """Покупает токены за точное количество DEL."""
        if not (token_address.startswith('0x') and recipient.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        return await self._send_request('buy_token_for_exact_del', {
            'token_address': token_address, 'amount_del': amount_del, 'recipient': recipient
        })

    async def buy_exact_token_for_del(self, token_address: str, amount_out: float, recipient: str) -> Dict[str, Any]:
        """Покупает точное количество токенов за DEL."""
        if not (token_address.startswith('0x') and recipient.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        return await self._send_request('buy_exact_token_for_del', {
            'token_address': token_address, 'amount_out': amount_out, 'recipient': recipient
        })

    async def sell_tokens_for_exact_del(self, token_address: str, amount_out: float, recipient: str) -> Dict[str, Any]:
        """Продает токены за точное количество DEL."""
        if not (token_address.startswith('0x') and recipient.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        return await self._send_request('sell_tokens_for_exact_del', {
            'token_address': token_address, 'amount_out': amount_out, 'recipient': recipient
        })

    async def sell_exact_tokens_for_del(self, token_address: str, amount_in: float, recipient: str) -> Dict[str, Any]:
        """Продает точное количество токенов за DEL."""
        if not (token_address.startswith('0x') and recipient.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        return await self._send_request('sell_exact_tokens_for_del', {
            'token_address': token_address, 'amount_in': amount_in, 'recipient': recipient
        })

    async def convert_token(self, token_address1: str, token_address2: str, amount_in: float,
                            recipient: str, token_center_address: str, sign: Optional[str] = None) -> Dict[str, Any]:
        """Конвертирует токены между собой."""
        if not (token_address1.startswith('0x') and token_address2.startswith('0x') and recipient.startswith(
                '0x') and token_center_address.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        payload = {'token_address1': token_address1, 'token_address2': token_address2,
                   'amount_in': amount_in, 'recipient': recipient, 'token_center_address': token_center_address}
        if sign:
            payload['sign'] = sign
        return await self._send_request('convert_token', payload)

    async def permit_token(self, token_address: str, owner: str, spender: str, amount: float) -> Dict[str, Any]:
        """Разрешает тратить токены с подписью."""
        if not (token_address.startswith('0x') and owner.startswith('0x') and spender.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        return await self._send_request('permit_token', {
            'token_address': token_address, 'owner': owner, 'spender': spender, 'amount': amount
        })

    async def update_token_identity(self, token_address: str, new_identity: str) -> Dict[str, Any]:
        """Обновляет идентификатор токена."""
        if not token_address.startswith('0x'):
            raise ValidationError("Адрес токена должен быть в формате 0x...")
        return await self._send_request('update_token_identity',
                                        {'token_address': token_address, 'new_identity': new_identity})

    async def update_token_max_supply(self, token_address: str, new_max_total_supply: float) -> Dict[str, Any]:
        """Обновляет максимальный объем токена."""
        if not token_address.startswith('0x'):
            raise ValidationError("Адрес токена должен быть в формате 0x...")
        return await self._send_request('update_token_max_supply', {
            'token_address': token_address, 'new_max_total_supply': new_max_total_supply
        })

    async def update_token_min_supply(self, token_address: str, new_min_total_supply: float) -> Dict[str, Any]:
        """Обновляет минимальный объем токена."""
        if not token_address.startswith('0x'):
            raise ValidationError("Адрес токена должен быть в формате 0x...")
        return await self._send_request('update_token_min_supply', {
            'token_address': token_address, 'new_min_total_supply': new_min_total_supply
        })

    async def create_nft_collection(self, symbol: str, name: str, contract_uri: str, refundable: bool,
                                    allow_mint: bool, reserveless: bool, type: str) -> Dict[str, Any]:
        """Создает коллекцию NFT (DRC721/DRC1155)."""
        if type not in ['DRC721', 'DRC1155']:
            raise ValidationError("Тип NFT должен быть DRC721 или DRC1155")
        return await self._send_request('create_nft_collection', {
            'symbol': symbol, 'name': name, 'contract_uri': contract_uri, 'refundable': refundable,
            'allow_mint': allow_mint, 'reserveless': reserveless, 'type': type
        })

    async def mint_nft(self, nft_collection_address: str, to: str, token_uri: str, reserve: Optional[float] = None,
                       token_address: Optional[str] = None, type: str = 'DRC721', token_id: Optional[int] = None,
                       amount: Optional[int] = None, sign: Optional[str] = None) -> Dict[str, Any]:
        """Минтит NFT."""
        if not (nft_collection_address.startswith('0x') and to.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        if type not in ['DRC721', 'DRC1155']:
            raise ValidationError("Тип NFT должен быть DRC721 или DRC1155")
        payload = {'nft_collection_address': nft_collection_address, 'to': to, 'token_uri': token_uri, 'type': type}
        if reserve is not None:
            payload['reserve'] = reserve
        if token_address:
            if not token_address.startswith('0x'):
                raise ValidationError("Адрес токена должен быть в формате 0x...")
            payload['token_address'] = token_address
        if token_id is not None:
            payload['token_id'] = token_id
        if amount is not None:
            payload['amount'] = amount
        if sign:
            payload['sign'] = sign
        return await self._send_request('mint_nft', payload)

    async def add_del_reserve_nft(self, nft_collection_address: str, token_id: int, reserve: float) -> Dict[str, Any]:
        """Добавляет резерв DEL для NFT."""
        if not nft_collection_address.startswith('0x'):
            raise ValidationError("Адрес коллекции NFT должен быть в формате 0x...")
        return await self._send_request('add_del_reserve_nft', {
            'nft_collection_address': nft_collection_address, 'token_id': token_id, 'reserve': reserve
        })

    async def add_token_reserve_nft(self, nft_collection_address: str, token_id: int, reserve: float,
                                    token_address: str, sign: Optional[str] = None) -> Dict[str, Any]:
        """Добавляет резерв токенов для NFT."""
        if not (nft_collection_address.startswith('0x') and token_address.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        payload = {'nft_collection_address': nft_collection_address, 'token_id': token_id,
                   'reserve': reserve, 'token_address': token_address}
        if sign:
            payload['sign'] = sign
        return await self._send_request('add_token_reserve_nft', payload)

    async def transfer_nft(self, nft_collection_address: str, from_address: str, to: str,
                           token_id: int, type: str, amount: Optional[int] = None) -> Dict[str, Any]:
        """Переводит NFT."""
        if not (nft_collection_address.startswith('0x') and from_address.startswith('0x') and to.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        if type not in ['DRC721', 'DRC1155']:
            raise ValidationError("Тип NFT должен быть DRC721 или DRC1155")
        payload = {'nft_collection_address': nft_collection_address, 'from': from_address,
                   'to': to, 'token_id': token_id, 'type': type}
        if amount is not None:
            payload['amount'] = amount
        return await self._send_request('transfer_nft', payload)

    async def transfer_batch_nft1155(self, nft_collection_address: str, from_address: str, to: str,
                                     token_ids: List[int], amounts: List[int]) -> Dict[str, Any]:
        """Переводит группу NFT (DRC1155)."""
        if not (nft_collection_address.startswith('0x') and from_address.startswith('0x') and to.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        return await self._send_request('transfer_batch_nft1155', {
            'nft_collection_address': nft_collection_address, 'from': from_address,
            'to': to, 'token_ids': token_ids, 'amounts': amounts
        })

    async def disable_mint_nft(self, nft_collection_address: str) -> Dict[str, Any]:
        """Отключает минтинг NFT."""
        if not nft_collection_address.startswith('0x'):
            raise ValidationError("Адрес коллекции NFT должен быть в формате 0x...")
        return await self._send_request('disable_mint_nft', {'nft_collection_address': nft_collection_address})

    async def burn_nft(self, nft_collection_address: str, token_id: int, type: str, amount: Optional[int] = None) -> Dict[
        str, Any]:
        """Сжигает NFT."""
        if not nft_collection_address.startswith('0x'):
            raise ValidationError("Адрес коллекции NFT должен быть в формате 0x...")
        if type not in ['DRC721', 'DRC1155']:
            raise ValidationError("Тип NFT должен быть DRC721 или DRC1155")
        payload = {'nft_collection_address': nft_collection_address, 'token_id': token_id, 'type': type}
        if amount is not None:
            payload['amount'] = amount
        return await self._send_request('burn_nft', payload)

    async def set_token_uri_nft(self, nft_collection_address: str, token_id: int, token_uri: str) -> Dict[str, Any]:
        """Устанавливает URI для NFT."""
        if not nft_collection_address.startswith('0x'):
            raise ValidationError("Адрес коллекции NFT должен быть в формате 0x...")
        return await self._send_request('set_token_uri_nft', {
            'nft_collection_address': nft_collection_address, 'token_id': token_id, 'token_uri': token_uri
        })

    async def approve_nft721(self, nft_collection_address: str, to: str, token_id: int) -> Dict[str, Any]:
        """Разрешает управление NFT (DRC721)."""
        if not (nft_collection_address.startswith('0x') and to.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        return await self._send_request('approve_nft721', {
            'nft_collection_address': nft_collection_address, 'to': to, 'token_id': token_id
        })

    async def approve_for_all_nft(self, nft_collection_address: str, to: str, approved: bool) -> Dict[str, Any]:
        """Разрешает управление всеми NFT."""
        if not (nft_collection_address.startswith('0x') and to.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        return await self._send_request('approve_for_all_nft', {
            'nft_collection_address': nft_collection_address, 'to': to, 'approved': approved
        })

    async def delegate_del(self, validator: str, amount: float, days: int) -> Tuple[bool, Optional[str], Optional[float]]:
        """Делегирует DEL валидатору."""
        if not validator.startswith('0x'):
            raise ValidationError("Адрес валидатора должен быть в формате 0x...")
        try:
            result = await self._send_request('delegate_del', {'validator': validator, 'amount': amount, 'days': days})
            return result.get('success', False), result.get('transactionHash'), result.get('totalAmount')
        except Exception as e:
            raise TransactionError(f"Ошибка делегирования DEL: {str(e)}")

    async def delegate_token(self, validator: str, token_address: str, amount: float,
                             days: int, sign: Optional[str] = None) -> Dict[str, Any]:
        """Делегирует токены."""
        if not (validator.startswith('0x') and token_address.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        payload = {'validator': validator, 'token_address': token_address, 'amount': amount, 'days': days}
        if sign:
            payload['sign'] = sign
        return await self._send_request('delegate_token', payload)

    async def delegate_nft(self, validator: str, nft_collection_address: str, token_id: int, type: str,
                           amount: Optional[int] = None, days: int = 0, sign: Optional[str] = None) -> Dict[str, Any]:
        """Делегирует NFT."""
        if not (validator.startswith('0x') and nft_collection_address.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        if type not in ['DRC721', 'DRC1155']:
            raise ValidationError("Тип NFT должен быть DRC721 или DRC1155")
        payload = {'validator': validator, 'nft_collection_address': nft_collection_address,
                   'token_id': token_id, 'type': type, 'days': days}
        if amount is not None:
            payload['amount'] = amount
        if sign:
            payload['sign'] = sign
        return await self._send_request('delegate_nft', payload)

    async def transfer_stake_token(self, validator: str, token: str, amount: float,
                                   new_validator: str, hold_timestamp: Optional[int] = None) -> Dict[str, Any]:
        """Переводит стейк токенов."""
        if not (validator.startswith('0x') and token.startswith('0x') and new_validator.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        payload = {'validator': validator, 'token': token, 'amount': amount, 'new_validator': new_validator}
        if hold_timestamp is not None:
            payload['hold_timestamp'] = hold_timestamp
        return await self._send_request('transfer_stake_token', payload)

    async def withdraw_stake_token(self, validator: str, token: str, amount: float) -> Dict[str, Any]:
        """Выводит стейк токенов."""
        if not (validator.startswith('0x') and token.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        return await self._send_request('withdraw_stake_token', {'validator': validator, 'token': token, 'amount': amount})

    async def stake_token_to_hold(self, validator: str, token: str, amount: float,
                                  old_hold_timestamp: int, days: int) -> Dict[str, Any]:
        """Переводит стейк токенов в режим удержания."""
        if not (validator.startswith('0x') and token.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        return await self._send_request('stake_token_to_hold', {
            'validator': validator, 'token': token, 'amount': amount,
            'old_hold_timestamp': old_hold_timestamp, 'days': days
        })

    async def stake_token_reset_hold(self, validator: str, delegator: str, token: str,
                                     hold_timestamp: int) -> Dict[str, Any]:
        """Сбрасывает удержание стейка токенов."""
        if not (validator.startswith('0x') and delegator.startswith('0x') and token.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        return await self._send_request('stake_token_reset_hold', {
            'validator': validator, 'delegator': delegator, 'token': token, 'hold_timestamp': hold_timestamp
        })

    async def stake_token_reset_hold_del(self, validator: str, delegator: str, hold_timestamp: int) -> Dict[str, Any]:
        """Сбрасывает удержание стейка DEL."""
        if not (validator.startswith('0x') and delegator.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        return await self._send_request('stake_token_reset_hold_del', {
            'validator': validator, 'delegator': delegator, 'hold_timestamp': hold_timestamp
        })

    async def withdraw_token_with_reset(self, validator: str, token: str, amount: float,
                                        hold_timestamps: List[int]) -> Dict[str, Any]:
        """Выводит токены с сбросом удержания."""
        if not (validator.startswith('0x') and token.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        return await self._send_request('withdraw_token_with_reset', {
            'validator': validator, 'token': token, 'amount': amount, 'hold_timestamps': hold_timestamps
        })

    async def transfer_token_with_reset(self, validator: str, token: str, amount: float,
                                        new_validator: str, hold_timestamps: List[int]) -> Dict[str, Any]:
        """Переводит токены с сбросом удержания."""
        if not (validator.startswith('0x') and token.startswith('0x') and new_validator.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        return await self._send_request('transfer_token_with_reset', {
            'validator': validator, 'token': token, 'amount': amount,
            'new_validator': new_validator, 'hold_timestamps': hold_timestamps
        })

    async def hold_token_with_reset(self, validator: str, token: str, amount: float,
                                    days: int, hold_timestamps: List[int]) -> Dict[str, Any]:
        """Устанавливает удержание токенов с сбросом."""
        if not (validator.startswith('0x') and token.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        return await self._send_request('hold_token_with_reset', {
            'validator': validator, 'token': token, 'amount': amount,
            'days': days, 'hold_timestamps': hold_timestamps
        })

    async def apply_penalty_to_stake_token(self, validator: str, delegator: str, token: str) -> Dict[str, Any]:
        """Применяет штраф к стейку токенов."""
        if not (validator.startswith('0x') and delegator.startswith('0x') and token.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        return await self._send_request('apply_penalty_to_stake_token', {
            'validator': validator, 'delegator': delegator, 'token': token
        })

    async def apply_penalties_to_stake_token(self, validator: str, delegator: str, token: str) -> Dict[str, Any]:
        """Применяет все штрафы к стейку токенов."""
        if not (validator.startswith('0x') and delegator.startswith('0x') and token.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        return await self._send_request('apply_penalties_to_stake_token', {
            'validator': validator, 'delegator': delegator, 'token': token
        })

    async def complete_stake_token(self, stake_indexes: List[int]) -> Dict[str, Any]:
        """Завершает замороженные стейки токенов."""
        return await self._send_request('complete_stake_token', {'stake_indexes': stake_indexes})

    async def transfer_stake_nft(self, validator: str, token: str, token_id: int, amount: int,
                                 new_validator: str, hold_timestamp: Optional[int] = None) -> Dict[str, Any]:
        """Переводит стейк NFT."""
        if not (validator.startswith('0x') and token.startswith('0x') and new_validator.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        payload = {'validator': validator, 'token': token, 'token_id': token_id,
                   'amount': amount, 'new_validator': new_validator}
        if hold_timestamp is not None:
            payload['hold_timestamp'] = hold_timestamp
        return await self._send_request('transfer_stake_nft', payload)

    async def withdraw_stake_nft(self, validator: str, token: str, token_id: int,
                                 amount: int, hold_timestamp: Optional[int] = None) -> Dict[str, Any]:
        """Выводит стейк NFT."""
        if not (validator.startswith('0x') and token.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        payload = {'validator': validator, 'token': token, 'token_id': token_id, 'amount': amount}
        if hold_timestamp is not None:
            payload['hold_timestamp'] = hold_timestamp
        return await self._send_request('withdraw_stake_nft', payload)

    async def stake_nft_to_hold(self, validator: str, token: str, token_id: int, amount: int,
                                old_hold_timestamp: int, days: int) -> Dict[str, Any]:
        """Переводит стейк NFT в режим удержания."""
        if not (validator.startswith('0x') and token.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        return await self._send_request('stake_nft_to_hold', {
            'validator': validator, 'token': token, 'token_id': token_id,
            'amount': amount, 'old_hold_timestamp': old_hold_timestamp, 'days': days
        })

    async def stake_nft_reset_hold(self, validator: str, delegator: str, token: str,
                                   token_id: int, hold_timestamp: int) -> Dict[str, Any]:
        """Сбрасывает удержание стейка NFT."""
        if not (validator.startswith('0x') and delegator.startswith('0x') and token.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        return await self._send_request('stake_nft_reset_hold', {
            'validator': validator, 'delegator': delegator, 'token': token,
            'token_id': token_id, 'hold_timestamp': hold_timestamp
        })

    async def withdraw_nft_with_reset(self, validator: str, token: str, token_id: int,
                                      amount: int, hold_timestamps: List[int]) -> Dict[str, Any]:
        """Выводит NFT с сбросом удержания."""
        if not (validator.startswith('0x') and token.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        return await self._send_request('withdraw_nft_with_reset', {
            'validator': validator, 'token': token, 'token_id': token_id,
            'amount': amount, 'hold_timestamps': hold_timestamps
        })

    async def transfer_nft_with_reset(self, validator: str, token: str, token_id: int,
                                      amount: int, new_validator: str, hold_timestamps: List[int]) -> Dict[str, Any]:
        """Переводит NFT с сбросом удержания."""
        if not (validator.startswith('0x') and token.startswith('0x') and new_validator.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        return await self._send_request('transfer_nft_with_reset', {
            'validator': validator, 'token': token, 'token_id': token_id,
            'amount': amount, 'new_validator': new_validator, 'hold_timestamps': hold_timestamps
        })

    async def hold_nft_with_reset(self, validator: str, token: str, token_id: int, amount: int,
                                  days: int, hold_timestamps: List[int]) -> Dict[str, Any]:
        """Устанавливает удержание NFT с сбросом."""
        if not (validator.startswith('0x') and token.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        return await self._send_request('hold_nft_with_reset', {
            'validator': validator, 'token': token, 'token_id': token_id,
            'amount': amount, 'days': days, 'hold_timestamps': hold_timestamps
        })

    async def complete_stake_nft(self, stake_indexes: List[int]) -> Dict[str, Any]:
        """Завершает замороженные стейки NFT."""
        return await self._send_request('complete_stake_nft', {'stake_indexes': stake_indexes})

    async def add_validator_with_del(self, reward_address: str, description: Dict[str, str],
                                     commission: str, amount: float) -> Dict[str, Any]:
        """Добавляет валидатора с DEL."""
        if not reward_address.startswith('0x'):
            raise ValidationError("Адрес вознаграждения должен быть в формате 0x...")
        return await self._send_request('add_validator_with_del', {
            'reward_address': reward_address, 'description': description,
            'commission': commission, 'amount': amount
        })

    async def add_validator_with_token(self, reward_address: str, description: Dict[str, str],
                                       commission: str, token_address: str, amount: float,
                                       sign: Optional[str] = None) -> Dict[str, Any]:
        """Добавляет валидатора с токеном."""
        if not (reward_address.startswith('0x') and token_address.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        payload = {'reward_address': reward_address, 'description': description,
                   'commission': commission, 'token_address': token_address, 'amount': amount}
        if sign:
            payload['sign'] = sign
        return await self._send_request('add_validator_with_token', payload)

    async def pause_validator(self, validator: str) -> Dict[str, Any]:
        """Приостанавливает валидатора."""
        if not validator.startswith('0x'):
            raise ValidationError("Адрес валидатора должен быть в формате 0x...")
        return await self._send_request('pause_validator', {'validator': validator})

    async def unpause_validator(self, validator: str) -> Dict[str, Any]:
        """Возобновляет валидатора."""
        if not validator.startswith('0x'):
            raise ValidationError("Адрес валидатора должен быть в формате 0x...")
        return await self._send_request('unpause_validator', {'validator': validator})

    async def update_validator_meta(self, reward_address: str, description: Dict[str, str],
                                    commission: str) -> Dict[str, Any]:
        """Обновляет метаданные валидатора."""
        if not reward_address.startswith('0x'):
            raise ValidationError("Адрес вознаграждения должен быть в формате 0x...")
        return await self._send_request('update_validator_meta', {
            'reward_address': reward_address, 'description': description, 'commission': commission
        })

    async def multi_send_token(self, data: List[Dict[str, Any]], memo: Optional[str] = None) -> Dict[str, Any]:
        """Выполняет множественные переводы токенов/DEL."""
        for item in data:
            if 'to' in item and not item['to'].startswith('0x'):
                raise ValidationError("Адреса получателей должны быть в формате 0x...")
        payload = {'data': data}
        if memo:
            payload['memo'] = memo
        return await self._send_request('multi_send_token', payload)

    async def multi_call(self, call_datas: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Выполняет кастомные вызовы контрактов."""
        for call in call_datas:
            if 'contract_address' in call and not call['contract_address'].startswith('0x'):
                raise ValidationError("Адреса контрактов должны быть в формате 0x...")
        return await self._send_request('multi_call', {'call_datas': call_datas})

    async def create_multisig(self, owner_data: List[Dict[str, Any]], weight_threshold: int) -> Dict[str, Any]:
        """Создает мультисиг кошелек."""
        for owner in owner_data:
            if 'address' in owner and not owner['address'].startswith('0x'):
                raise ValidationError("Адреса владельцев должны быть в формате 0x...")
        return await self._send_request('create_multisig', {'owner_data': owner_data, 'weight_threshold': weight_threshold})

    async def build_tx_send_del(self, multisig_address: str, to: str, amount: float) -> Dict[str, Any]:
        """Создает транзакцию для отправки DEL."""
        if not (multisig_address.startswith('0x') and to.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        return await self._send_request('build_tx_send_del', {
            'multisig_address': multisig_address, 'to': to, 'amount': amount
        })

    async def build_tx_send_token(self, multisig_address: str, token_address: str, to: str, amount: float) -> Dict[
        str, Any]:
        """Создает транзакцию для отправки токенов."""
        if not (multisig_address.startswith('0x') and token_address.startswith('0x') and to.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        return await self._send_request('build_tx_send_token', {
            'multisig_address': multisig_address, 'token_address': token_address, 'to': to, 'amount': amount
        })

    async def build_tx_send_nft(self, multisig_address: str, token_address: str, to: str,
                                token_id: int, type: str, amount: Optional[int] = None) -> Dict[str, Any]:
        """Создает транзакцию для отправки NFT."""
        if not (multisig_address.startswith('0x') and token_address.startswith('0x') and to.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        if type not in ['DRC721', 'DRC1155']:
            raise ValidationError("Тип NFT должен быть DRC721 или DRC1155")
        payload = {'multisig_address': multisig_address, 'token_address': token_address,
                   'to': to, 'token_id': token_id, 'type': type}
        if amount is not None:
            payload['amount'] = amount
        return await self._send_request('build_tx_send_nft', payload)

    async def sign_multisig_tx(self, multisig_address: str, safe_tx: Dict[str, Any]) -> Dict[str, Any]:
        """Подписывает мультисиг транзакцию."""
        if not multisig_address.startswith('0x'):
            raise ValidationError("Адрес мультисиг кошелька должен быть в формате 0x...")
        return await self._send_request('sign_multisig_tx', {'multisig_address': multisig_address, 'safe_tx': safe_tx})

    async def approve_hash_multisig(self, multisig_address: str, safe_tx: Dict[str, Any]) -> Dict[str, Any]:
        """Подтверждает хэш мультисиг транзакции."""
        if not multisig_address.startswith('0x'):
            raise ValidationError("Адрес мультисиг кошелька должен быть в формате 0x...")
        return await self._send_request('approve_hash_multisig', {'multisig_address': multisig_address, 'safe_tx': safe_tx})

    async def execute_multisig_tx(self, multisig_address: str, safe_tx: Dict[str, Any],
                                  signatures: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Выполняет мультисиг транзакцию."""
        if not multisig_address.startswith('0x'):
            raise ValidationError("Адрес мультисиг кошелька должен быть в формате 0x...")
        return await self._send_request('execute_multisig_tx', {
            'multisig_address': multisig_address, 'safe_tx': safe_tx, 'signatures': signatures
        })

    async def get_current_approve_transactions(self, multisig_address: str) -> Dict[str, Any]:
        """Получает текущие подтвержденные транзакции."""
        if not multisig_address.startswith('0x'):
            raise ValidationError("Адрес мультисиг кошелька должен быть в формате 0x...")
        return await self._send_request('get_current_approve_transactions', {'multisig_address': multisig_address})

    async def get_expired_approve_transactions(self, multisig_address: str) -> Dict[str, Any]:
        """Получает просроченные подтвержденные транзакции."""
        if not multisig_address.startswith('0x'):
            raise ValidationError("Адрес мультисиг кошелька должен быть в формате 0x...")
        return await self._send_request('get_expired_approve_transactions', {'multisig_address': multisig_address})

    async def bridge_transfer_native(self, to: str, amount: float, from_chain_id: int, to_chain_id: int) -> Dict[str, Any]:
        """Переводит DEL/ETH/BNB через мост."""
        if not to.startswith('0x'):
            raise ValidationError("Адрес получателя должен быть в формате 0x...")
        return await self._send_request('bridge_transfer_native', {
            'to': to, 'amount': amount, 'from_chain_id': from_chain_id, 'to_chain_id': to_chain_id
        })

    async def bridge_transfer_tokens(self, token_address: str, to: str, amount: float,
                                     from_chain_id: int, to_chain_id: int) -> Dict[str, Any]:
        """Переводит токены через мост."""
        if not (token_address.startswith('0x') and to.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        return await self._send_request('bridge_transfer_tokens', {
            'token_address': token_address, 'to': to, 'amount': amount,
            'from_chain_id': from_chain_id, 'to_chain_id': to_chain_id
        })

    async def bridge_complete_transfer(self, to_chain_id: int, encoded_vm: str, unwrap_weth: bool) -> Dict[str, Any]:
        """Завершает перевод через мост."""
        return await self._send_request('bridge_complete_transfer', {
            'to_chain_id': to_chain_id, 'encoded_vm': encoded_vm, 'unwrap_weth': unwrap_weth
        })

    async def create_checks_del(self, passwords: List[str], amount: float, block_offset: int) -> Dict[str, Any]:
        """Создает чеки для DEL."""
        if not passwords or amount <= 0 or block_offset < 0:
            raise ValidationError("Неверные параметры для создания чеков")
        return await self._send_request('create_checks_del', {
            'passwords': passwords, 'amount': amount, 'block_offset': block_offset
        })

    async def create_checks_token(self, passwords: List[str], amount: float, block_offset: int,
                                  token_address: str, sign: Optional[str] = None) -> Dict[str, Any]:
        """Создает чеки для токенов."""
        if not (passwords and token_address.startswith('0x') and amount > 0 and block_offset >= 0):
            raise ValidationError("Неверные параметры для создания чеков")
        payload = {'passwords': passwords, 'amount': amount, 'block_offset': block_offset, 'token_address': token_address}
        if sign:
            payload['sign'] = sign
        return await self._send_request('create_checks_token', payload)

    async def redeem_checks(self, passwords: List[str], checks: List[str]) -> Dict[str, Any]:
        """Погашает чеки."""
        if not (passwords and checks):
            raise ValidationError("Списки паролей и чеков не могут быть пустыми")
        return await self._send_request('redeem_checks', {'passwords': passwords, 'checks': checks})

    async def get_balance(self, address: str) -> Dict[str, Any]:
        """Получает баланс DEL."""
        if not address.startswith('0x'):
            raise ValidationError("Адрес должен быть в формате 0x...")
        return await self._send_request('get_balance', {'address': address})

    async def get_balance_eth(self, address: str) -> Dict[str, Any]:
        """Получает баланс ETH."""
        if not address.startswith('0x'):
            raise ValidationError("Адрес должен быть в формате 0x...")
        return await self._send_request('get_balance_eth', {'address': address})

    async def get_balance_bnb(self, address: str) -> Dict[str, Any]:
        """Получает баланс BNB."""
        if not address.startswith('0x'):
            raise ValidationError("Адрес должен быть в формате 0x...")
        return await self._send_request('get_balance_bnb', {'address': address})

    async def check_token_exists(self, token_address: str) -> bool:
        """Проверяет существование токена."""
        if not token_address.startswith('0x'):
            raise ValidationError("Адрес токена должен быть в формате 0x...")
        return await self._send_request('check_token_exists', {'token_address': token_address})

    async def get_address_token_by_symbol(self, symbol: str) -> str:
        """Получает адрес токена по символу."""
        if not symbol:
            raise ValidationError("Символ токена не может быть пустым")
        return await self._send_request('get_address_token_by_symbol', {'symbol': symbol})

    async def get_commission_symbol(self, symbol: str) -> float:
        """Получает комиссию за создание токена."""
        if not symbol:
            raise ValidationError("Символ токена не может быть пустым")
        return await self._send_request('get_commission_symbol', {'symbol': symbol})

    async def calculate_buy_output(self, token_address: str, amount_del: float) -> float:
        """Рассчитывает выход токенов при покупке за DEL."""
        if not token_address.startswith('0x'):
            raise ValidationError("Адрес токена должен быть в формате 0x...")
        return await self._send_request('calculate_buy_output', {'token_address': token_address, 'amount_del': amount_del})

    async def calculate_buy_input(self, token_address: str, amount_tokens: float) -> float:
        """Рассчитывает вход DEL для покупки токенов."""
        if not token_address.startswith('0x'):
            raise ValidationError("Адрес токена должен быть в формате 0x...")
        return await self._send_request('calculate_buy_input',
                                        {'token_address': token_address, 'amount_tokens': amount_tokens})

    async def calculate_sell_input(self, token_address: str, amount_del: float) -> float:
        """Рассчитывает вход токенов для продажи за DEL."""
        if not token_address.startswith('0x'):
            raise ValidationError("Адрес токена должен быть в формате 0x...")
        return await self._send_request('calculate_sell_input', {'token_address': token_address, 'amount_del': amount_del})

    async def calculate_sell_output(self, token_address: str, amount_tokens: float) -> float:
        """Рассчитывает выход DEL для продажи токенов."""
        if not token_address.startswith('0x'):
            raise ValidationError("Адрес токена должен быть в формате 0x...")
        return await self._send_request('calculate_sell_output',
                                        {'token_address': token_address, 'amount_tokens': amount_tokens})

    async def get_sign_permit_token(self, token_address: str, spender: str, amount: float) -> str:
        """Получает подпись для разрешения токенов."""
        if not (token_address.startswith('0x') and spender.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        return await self._send_request('get_sign_permit_token', {
            'token_address': token_address, 'spender': spender, 'amount': amount
        })

    async def allowance_token(self, token_address: str, owner: str, spender: str) -> bool:
        """Проверяет разрешение на трату токенов."""
        if not (token_address.startswith('0x') and owner.startswith('0x') and spender.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        return await self._send_request('allowance_token', {
            'token_address': token_address, 'owner': owner, 'spender': spender
        })

    async def balance_of_token(self, token_address: str, account: str) -> float:
        """Получает баланс токенов."""
        if not (token_address.startswith('0x') and account.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        return await self._send_request('balance_of_token', {'token_address': token_address, 'account': account})

    async def supports_interface_token(self, token_address: str, interface_id: str) -> bool:
        """Проверяет поддержку интерфейса токена."""
        if not token_address.startswith('0x'):
            raise ValidationError("Адрес токена должен быть в формате 0x...")
        return await self._send_request('supports_interface_token', {
            'token_address': token_address, 'interface_id': interface_id
        })

    async def get_nft_type(self, nft_collection_address: str) -> str:
        """Получает тип NFT из Subgraph."""
        if not nft_collection_address.startswith('0x'):
            raise ValidationError("Адрес коллекции NFT должен быть в формате 0x...")
        return await self._send_request('get_nft_type', {'nft_collection_address': nft_collection_address})

    async def get_nft_type_from_contract(self, nft_collection_address: str) -> str:
        """Получает тип NFT из контракта."""
        if not nft_collection_address.startswith('0x'):
            raise ValidationError("Адрес коллекции NFT должен быть в формате 0x...")
        return await self._send_request('get_nft_type_from_contract', {'nft_collection_address': nft_collection_address})

    async def get_approved_nft721(self, nft_collection_address: str, token_id: int) -> str:
        """Получает адрес, одобренный для NFT (DRC721)."""
        if not nft_collection_address.startswith('0x'):
            raise ValidationError("Адрес коллекции NFT должен быть в формате 0x...")
        return await self._send_request('get_approved_nft721', {
            'nft_collection_address': nft_collection_address, 'token_id': token_id
        })

    async def is_approved_for_all_nft(self, nft_collection_address: str, owner: str, spender: str) -> bool:
        """Проверяет разрешение для всех NFT."""
        if not (nft_collection_address.startswith('0x') and owner.startswith('0x') and spender.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        return await self._send_request('is_approved_for_all_nft', {
            'nft_collection_address': nft_collection_address, 'owner': owner, 'spender': spender
        })

    async def owner_of_nft721(self, nft_collection_address: str, token_id: int) -> str:
        """Получает владельца NFT (DRC721)."""
        if not nft_collection_address.startswith('0x'):
            raise ValidationError("Адрес коллекции NFT должен быть в формате 0x...")
        return await self._send_request('owner_of_nft721', {
            'nft_collection_address': nft_collection_address, 'token_id': token_id
        })

    async def get_token_uri_nft(self, nft_collection_address: str, token_id: int) -> str:
        """Получает URI токена NFT."""
        if not nft_collection_address.startswith('0x'):
            raise ValidationError("Адрес коллекции NFT должен быть в формате 0x...")
        return await self._send_request('get_token_uri_nft', {
            'nft_collection_address': nft_collection_address, 'token_id': token_id
        })

    async def get_allow_mint_nft(self, nft_collection_address: str) -> bool:
        """Проверяет, разрешен ли минтинг NFT."""
        if not nft_collection_address.startswith('0x'):
            raise ValidationError("Адрес коллекции NFT должен быть в формате 0x...")
        return await self._send_request('get_allow_mint_nft', {'nft_collection_address': nft_collection_address})

    async def balance_of_nft(self, nft_collection_address: str, account: str,
                             type: str, token_id: Optional[int] = None) -> int:
        """Получает баланс NFT."""
        if not (nft_collection_address.startswith('0x') and account.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        if type not in ['DRC721', 'DRC1155']:
            raise ValidationError("Тип NFT должен быть DRC721 или DRC1155")
        payload = {'nft_collection_address': nft_collection_address, 'account': account, 'type': type}
        if token_id is not None:
            payload['token_id'] = token_id
        return await self._send_request('balance_of_nft', payload)

    async def supports_interface_nft(self, nft_collection_address: str, interface_id: str) -> bool:
        """Проверяет поддержку интерфейса NFT."""
        if not nft_collection_address.startswith('0x'):
            raise ValidationError("Адрес коллекции NFT должен быть в формате 0x...")
        return await self._send_request('supports_interface_nft', {
            'nft_collection_address': nft_collection_address, 'interface_id': interface_id
        })

    async def get_rate_nft1155(self, nft_collection_address: str, token_id: int) -> float:
        """Получает курс NFT (DRC1155)."""
        if not nft_collection_address.startswith('0x'):
            raise ValidationError("Адрес коллекции NFT должен быть в формате 0x...")
        return await self._send_request('get_rate_nft1155', {
            'nft_collection_address': nft_collection_address, 'token_id': token_id
        })

    async def calc_reserve_nft1155(self, nft_collection_address: str, token_id: int, quantity: int) -> float:
        """Рассчитывает резерв для минтинга NFT (DRC1155)."""
        if not nft_collection_address.startswith('0x'):
            raise ValidationError("Адрес коллекции NFT должен быть в формате 0x...")
        return await self._send_request('calc_reserve_nft1155', {
            'nft_collection_address': nft_collection_address, 'token_id': token_id, 'quantity': quantity
        })

    async def get_sign_permit_nft(self, nft_collection_address: str, spender: str,
                                  type: str, token_id: Optional[int] = None) -> str:
        """Получает подпись для разрешения NFT."""
        if not (nft_collection_address.startswith('0x') and spender.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        if type not in ['DRC721', 'DRC1155']:
            raise ValidationError("Тип NFT должен быть DRC721 или DRC1155")
        payload = {'nft_collection_address': nft_collection_address, 'spender': spender, 'type': type}
        if token_id is not None:
            payload['token_id'] = token_id
        return await self._send_request('get_sign_permit_nft', payload)

    async def get_reserve_nft(self, nft_collection_address: str, token_id: int) -> Dict[str, Any]:
        """Получает резерв NFT."""
        if not nft_collection_address.startswith('0x'):
            raise ValidationError("Адрес коллекции NFT должен быть в формате 0x...")
        return await self._send_request('get_reserve_nft', {
            'nft_collection_address': nft_collection_address, 'token_id': token_id
        })

    async def get_refundable_nft(self, nft_collection_address: str) -> bool:
        """Проверяет, возвращается ли резерв при сжигании NFT."""
        if not nft_collection_address.startswith('0x'):
            raise ValidationError("Адрес коллекции NFT должен быть в формате 0x...")
        return await self._send_request('get_refundable_nft', {'nft_collection_address': nft_collection_address})

    async def get_supply_nft1155(self, nft_collection_address: str, token_id: int) -> int:
        """Получает объем NFT (DRC1155)."""
        if not nft_collection_address.startswith('0x'):
            raise ValidationError("Адрес коллекции NFT должен быть в формате 0x...")
        return await self._send_request('get_supply_nft1155', {
            'nft_collection_address': nft_collection_address, 'token_id': token_id
        })

    async def get_token_stakes_page_by_member(self, account: str, size: int, offset: int) -> List[Dict[str, Any]]:
        """Получает стейки токенов по адресу."""
        if not account.startswith('0x'):
            raise ValidationError("Адрес должен быть в формате 0x...")
        return await self._send_request('get_token_stakes_page_by_member', {
            'account': account, 'size': size, 'offset': offset
        })

    async def get_frozen_stakes_queue_token(self) -> List[Dict[str, Any]]:
        """Получает очередь замороженных стейков токенов."""
        return await self._send_request('get_frozen_stakes_queue_token', {})

    async def get_freeze_time_token(self) -> Dict[str, int]:
        """Получает время заморозки токенов."""
        return await self._send_request('get_freeze_time_token', {})

    async def get_stake_token(self, validator: str, delegator: str, token_address: str) -> Dict[str, Any]:
        """Получает данные стейка токена."""
        if not (validator.startswith('0x') and delegator.startswith('0x') and token_address.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        return await self._send_request('get_stake_token', {
            'validator': validator, 'delegator': delegator, 'token_address': token_address
        })

    async def get_stake_id_token(self, validator: str, delegator: str, token_address: str) -> str:
        """Получает ID стейка токена."""
        if not (validator.startswith('0x') and delegator.startswith('0x') and token_address.startswith('0x')):
            raise ValidationError("Адреса должны быть в формате 0x...")
        return await self._send_request('get_stake_id_token', {
            'validator': validator, 'delegator': delegator, 'token_address': token_address
        })

    async def get_nft_stakes_page_by_member(self, account: str, size: int, offset: int) -> List[Dict[str, Any]]:
        """Получает стейки NFT по адресу."""
        if not account.startswith('0x'):
            raise ValidationError("Адрес должен быть в формате 0x...")
        return await self._send_request('get_nft_stakes_page_by_member', {
            'account': account, 'size': size, 'offset': offset
        })

    async def get_frozen_stakes_queue_nft(self) -> List[Dict[str, Any]]:
        """Получает очередь замороженных стейков NFT."""
        return await self._send_request('get_frozen_stakes_queue_nft', {})

    async def get_freeze_time_nft(self) -> Dict[str, int]:
        """Получает время заморозки NFT."""
        return await self._send_request('get_freeze_time_nft', {})

    async def get_validator_status(self, validator: str) -> Dict[str, Any]:
        """Получает статус валидатора."""
        if not validator.startswith('0x'):
            raise ValidationError("Адрес валидатора должен быть в формате 0x...")
        return await self._send_request('get_validator_status', {'validator': validator})

    async def validator_is_active(self, validator: str) -> bool:
        """Проверяет, активен ли валидатор."""
        if not validator.startswith('0x'):
            raise ValidationError("Адрес валидатора должен быть в формате 0x...")
        return await self._send_request('validator_is_active', {'validator': validator})

    async def validator_is_member(self, validator: str) -> bool:
        """Проверяет, является ли адрес валидатором."""
        if not validator.startswith('0x'):
            raise ValidationError("Адрес валидатора должен быть в формате 0x...")
        return await self._send_request('validator_is_member', {'validator': validator})

    async def get_decimal_contracts(self) -> List[Dict[str, Any]]:
        """Получает контракты Decimal."""
        return await self._send_request('get_decimal_contracts', {})

    async def get_validators(self) -> List[Dict[str, Any]]:
        """Получает список валидаторов."""
        return await self._send_request('get_validators', {})

    async def get_validator(self, validator: str) -> Dict[str, Any]:
        """Получает данные валидатора."""
        if not validator.startswith('0x'):
            raise ValidationError("Адрес валидатора должен быть в формате 0x...")
        return await self._send_request('get_validator', {'validator': validator})

    async def get_validator_penalties(self, validator: str, first: int, skip: int) -> List[Dict[str, Any]]:
        """Получает штрафы валидатора."""
        if not validator.startswith('0x'):
            raise ValidationError("Адрес валидатора должен быть в формате 0x...")
        return await self._send_request('get_validator_penalties', {
            'validator': validator, 'first': first, 'skip': skip
        })

    async def get_validator_penalties_from_block(self, validator: str, block_number: int,
                                                 first: int, skip: int) -> List[Dict[str, Any]]:
        """Получает штрафы валидатора с определенного блока."""
        if not validator.startswith('0x'):
            raise ValidationError("Адрес валидатора должен быть в формате 0x...")
        return await self._send_request('get_validator_penalties_from_block', {
            'validator': validator, 'block_number': block_number, 'first': first, 'skip': skip
        })

    async def get_sum_amount_to_penalty(self) -> Dict[str, Any]:
        """Получает сумму штрафов."""
        return await self._send_request('get_sum_amount_to_penalty', {})

    async def get_tokens(self, first: int, skip: int) -> List[Dict[str, Any]]:
        """Получает список токенов."""
        return await self._send_request('get_tokens', {'first': first, 'skip': skip})

    async def get_tokens_by_owner(self, owner: str, first: int, skip: int) -> List[Dict[str, Any]]:
        """Получает токены по владельцу."""
        if not owner.startswith('0x'):
            raise ValidationError("Адрес владельца должен быть в формате 0x...")
        return await self._send_request('get_tokens_by_owner', {'owner': owner, 'first': first, 'skip': skip})

    async def get_token_by_symbol(self, symbol: str) -> Dict[str, Any]:
        """Получает токен по символу."""
        if not symbol:
            raise ValidationError("Символ токена не может быть пустым")
        return await self._send_request('get_token_by_symbol', {'symbol': symbol})

    async def get_token_by_address(self, token_address: str) -> Dict[str, Any]:
        """Получает токен по адресу."""
        if not token_address.startswith('0x'):
            raise ValidationError("Адрес токена должен быть в формате 0x...")
        return await self._send_request('get_token_by_address', {'token_address': token_address})

    async def get_address_balances(self, account: str, first: int, skip: int) -> List[Dict[str, Any]]:
        """Получает балансы адреса."""
        if not account.startswith('0x'):
            raise ValidationError("Адрес должен быть в формате 0x...")
        return await self._send_request('get_address_balances', {'account': account, 'first': first, 'skip': skip})

    async def get_stakes(self, first: int, skip: int) -> List[Dict[str, Any]]:
        """Получает список стейков."""
        return await self._send_request('get_stakes', {'first': first, 'skip': skip})

    async def get_stakes_by_address(self, delegator: str, first: int, skip: int) -> List[Dict[str, Any]]:
        """Получает стейки по адресу."""
        if not delegator.startswith('0x'):
            raise ValidationError("Адрес делегатора должен быть в формате 0x...")
        return await self._send_request('get_stakes_by_address', {'delegator': delegator, 'first': first, 'skip': skip})

    async def get_stakes_by_validator(self, validator: str, first: int, skip: int) -> List[Dict[str, Any]]:
        """Получает стейки по валидатору."""
        if not validator.startswith('0x'):
            raise ValidationError("Адрес валидатора должен быть в формате 0x...")
        return await self._send_request('get_stakes_by_validator', {'validator': validator, 'first': first, 'skip': skip})

    async def get_transfer_stakes(self, first: int, skip: int) -> List[Dict[str, Any]]:
        """Получает переводы стейков."""
        return await self._send_request('get_transfer_stakes', {'first': first, 'skip': skip})

    async def get_transfer_stakes_by_address(self, delegator: str, first: int, skip: int) -> dict[str, Any]:
        """Получает переводы стейков по адресу."""
        if not delegator.startswith('0x'):
            raise ValidationError("Адрес делегатора должен быть в формате 0x...")
        return await self._send_request('get_transfer_stakes_by_address', {
            'delegator': delegator, 'first': first, 'skip': skip
        })

    async def get_withdraw_stakes(self, first: int, skip: int) -> List[Dict[str, Any]]:
        """Получает выводы стейков."""
        return await self._send_request('get_withdraw_stakes', {'first': first, 'skip': skip})

    async def get_withdraw_stakes_by_address(self, delegator: str, first: int, skip: int) -> List[Dict[str, Any]]:
        """Получает выводы стейков по адресу."""
        if not delegator.startswith('0x'):
            raise ValidationError("Адрес делегатора должен быть в формате 0x...")
        return await self._send_request('get_withdraw_stakes_by_address', {
            'delegator': delegator, 'first': first, 'skip': skip})

    async def get_nft_collections(self, first: int, skip: int) -> List[Dict[str, Any]]:
        """Получает список коллекций NFT."""
        return await self._send_request('get_nft_collections', {'first': first, 'skip': skip})

    async def get_nft_collections_by_creator(self, owner: str, first: int, skip: int) -> dict[str, Any]:
        """Получает коллекции NFT по создателю."""
        if not owner.startswith('0x'):
            raise ValidationError("Адрес создателя должен быть в формате 0x...")
        return await self._send_request('get_nft_collections_by_creator', {
            'owner': owner, 'first': first, 'skip': skip
        })
