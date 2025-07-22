const net = require('net');
const fs = require('fs');
const path = require('path');
const { Fernet, encode, decode } = require('fernet');
require('dotenv').config();

// Подключаем SDK
const dscSdkPath = path.resolve(__dirname, 'dsc-js-sdk');
const SDK = require(dscSdkPath);
const { Wallet, DecimalEVM, DecimalNetworks, Subgraph } = SDK;

// Конфигурация
const SOCKET_PATH = process.env.SOCKET_PATH || '/tmp/decimal_ipc.sock';
const ENCRYPTION_KEY = process.env.ENCRYPTION_KEY;
if (!ENCRYPTION_KEY) throw new Error('ENCRYPTION_KEY not set in .env');

const fernet = new Fernet({ secret: encode(ENCRYPTION_KEY) });

// Удаляем старый сокет
if (fs.existsSync(SOCKET_PATH)) {
    fs.unlinkSync(SOCKET_PATH);
}

// Хранилище кошельков и EVM
const tempWallets = {};
const decimalEVMs = {};
const subgraphs = {};

async function getDecimalEVM(walletId) {
    if (decimalEVMs[walletId]) return decimalEVMs[walletId];

    const wallet = tempWallets[walletId];
    if (!wallet) throw new Error(`Кошелёк "${walletId}" не найден`);

    decimalEVMs[walletId] = new DecimalEVM(wallet, DecimalNetworks.mainnet);
    await decimalEVMs[walletId].connect(); // Инициализация всех контрактов
    console.log(`✅ DecimalEVM создан для ${walletId}`);
    return decimalEVMs[walletId];
}

async function getSubgraph() {
    if (subgraphs['mainnet']) return subgraphs['mainnet'];

    subgraphs['mainnet'] = new Subgraph(DecimalNetworks.mainnet);
    console.log(`✅ Subgraph подключён для mainnet`);
    return subgraphs['mainnet'];
}

// Сервер
const server = net.createServer(async (socket) => {
    console.log('🔌 Клиент подключён');

    socket.on('data', async (data) => {
        try {
            const request = JSON.parse(data.toString());
            const { action, payload } = request;

            let result;
            const decimalEVM = await getDecimalEVM(payload.wallet_id);
            const subgraph = await getSubgraph();

            switch (action) {
                // Wallet Management
                case 'create_wallet':
                    const { mnemonic: encryptedMnemonic, wallet_id } = payload;
                    if (!encryptedMnemonic || !wallet_id) throw new Error('Не указан wallet_id или mnemonic');

                    const mnemonic = fernet.decrypt(decode(encryptedMnemonic)).toString();
                    const bip39 = require('bip39');
                    if (!bip39.validateMnemonic(mnemonic)) {
                        throw new Error('❌ Неверная мнемоника');
                    }

                    tempWallets[wallet_id] = new Wallet(mnemonic);
                    result = { success: true, wallet_id, address: tempWallets[wallet_id].evmAddress };
                    break;

                // DEL Operations
                case 'send_del':
                    const amountToSend = decimalEVM.parseEther(payload.amount);
                    result = await decimalEVM.sendDEL(payload.to, amountToSend);
                    break;

                case 'burn_del':
                    const amountToBurn = decimalEVM.parseEther(payload.amount);
                    result = await decimalEVM.burnDEL(amountToBurn);
                    break;

                // Token Operations
                case 'create_token':
                    const tokenParams = {
                        creator: tempWallets[payload.wallet_id].evmAddress,
                        symbol: payload.symbol,
                        name: payload.name,
                        crr: payload.crr,
                        initialMint: decimalEVM.parseEther(payload.initialMint),
                        minTotalSupply: decimalEVM.parseEther(payload.minTotalSupply),
                        maxTotalSupply: decimalEVM.parseEther(payload.maxTotalSupply),
                        identity: payload.identity
                    };
                    const commission = calculateTokenCommission(payload.symbol);
                    const reserve = decimalEVM.parseEther(Number(payload.initialMint) + commission);
                    result = await decimalEVM.createToken(tokenParams, reserve);
                    break;

                case 'create_token_reserveless':
                    const reservelessParams = {
                        name: payload.name,
                        symbol: payload.symbol,
                        mintable: payload.mintable,
                        burnable: payload.burnable,
                        initialMint: decimalEVM.parseEther(payload.initialMint),
                        cap: payload.cap ? decimalEVM.parseEther(payload.cap) : undefined,
                        identity: payload.identity
                    };
                    result = await decimalEVM.createTokenReserveless(
                        reservelessParams.name,
                        reservelessParams.symbol,
                        reservelessParams.mintable,
                        reservelessParams.burnable,
                        reservelessParams.initialMint,
                        reservelessParams.cap,
                        reservelessParams.identity
                    );
                    break;

                case 'convert_to_del':
                    const convertAmount = decimalEVM.parseEther(payload.amount);
                    const estimateGas = decimalEVM.parseEther(payload.estimateGas);
                    const signConvert = await decimalEVM.getSignPermitToken(payload.tokenAddress, payload.gasCenterAddress, convertAmount);
                    result = await decimalEVM.convertToDEL(
                        tempWallets[payload.wallet_id].evmAddress,
                        payload.tokenAddress,
                        convertAmount,
                        estimateGas,
                        signConvert
                    );
                    break;

                case 'approve_token':
                    result = await decimalEVM.approveToken(payload.tokenAddress, payload.spender, decimalEVM.parseEther(payload.amount));
                    break;

                case 'transfer_token':
                    result = await decimalEVM.transferToken(payload.tokenAddress, payload.to, decimalEVM.parseEther(payload.amount));
                    break;

                case 'transfer_from_token':
                    result = await decimalEVM.transferFromToken(payload.tokenAddress, payload.from, payload.to, decimalEVM.parseEther(payload.amount));
                    break;

                case 'burn_token':
                    result = await decimalEVM.burnToken(payload.tokenAddress, decimalEVM.parseEther(payload.amount));
                    break;

                case 'buy_token_for_exact_del':
                    const buyDelAmount = decimalEVM.parseEther(payload.amountDel);
                    const amountOutMin = await decimalEVM.calculateBuyOutput(payload.tokenAddress, buyDelAmount);
                    result = await decimalEVM.buyTokenForExactDEL(payload.tokenAddress, buyDelAmount, amountOutMin, payload.recipient);
                    break;

                case 'buy_exact_token_for_del':
                    const buyTokenAmount = decimalEVM.parseEther(payload.amountOut);
                    const amountDel = await decimalEVM.calculateBuyInput(payload.tokenAddress, buyTokenAmount);
                    result = await decimalEVM.buyExactTokenForDEL(payload.tokenAddress, amountDel, buyTokenAmount, payload.recipient);
                    break;

                case 'sell_tokens_for_exact_del':
                    const sellDelAmount = decimalEVM.parseEther(payload.amountOut);
                    const amountInMax = await decimalEVM.calculateSellInput(payload.tokenAddress, sellDelAmount);
                    result = await decimalEVM.sellTokensForExactDEL(payload.tokenAddress, sellDelAmount, amountInMax, payload.recipient);
                    break;

                case 'sell_exact_tokens_for_del':
                    const sellTokenAmount = decimalEVM.parseEther(payload.amountIn);
                    const amountOutMinSell = await decimalEVM.calculateSellOutput(payload.tokenAddress, sellTokenAmount);
                    result = await decimalEVM.sellExactTokensForDEL(payload.tokenAddress, sellTokenAmount, amountOutMinSell, payload.recipient);
                    break;

                case 'convert_token':
                    const convertTokenAmount = decimalEVM.parseEther(payload.amountIn);
                    const futureDEL = await decimalEVM.calculateSellOutput(payload.tokenAddress1, convertTokenAmount);
                    const amountOutMinConvert = await decimalEVM.calculateBuyOutput(payload.tokenAddress2, futureDEL);
                    const signConvertToken = payload.sign ? payload.sign : await decimalEVM.getSignPermitToken(payload.tokenAddress1, payload.tokenCenterAddress, convertTokenAmount);
                    result = await decimalEVM.convertToken(
                        payload.tokenAddress1,
                        payload.tokenAddress2,
                        convertTokenAmount,
                        amountOutMinConvert,
                        payload.recipient,
                        signConvertToken
                    );
                    break;

                case 'permit_token':
                    const signPermit = await decimalEVM.getSignPermitToken(payload.tokenAddress, payload.spender, decimalEVM.parseEther(payload.amount));
                    result = await decimalEVM.permitToken(payload.tokenAddress, payload.owner, payload.spender, decimalEVM.parseEther(payload.amount), signPermit);
                    break;

                case 'update_token_identity':
                    result = await decimalEVM.updateTokenIdentity(payload.tokenAddress, payload.newIdentity);
                    break;

                case 'update_token_max_supply':
                    result = await decimalEVM.updateTokenMaxTotalSupply(payload.tokenAddress, decimalEVM.parseEther(payload.newMaxTotalSupply));
                    break;

                case 'update_token_min_supply':
                    result = await decimalEVM.updateTokenMinTotalSupply(payload.tokenAddress, decimalEVM.parseEther(payload.newMinTotalSupply));
                    break;

                // NFT Operations
                case 'create_nft_collection':
                    const nftParams = {
                        creator: tempWallets[payload.wallet_id].evmAddress,
                        symbol: payload.symbol,
                        name: payload.name,
                        contractURI: payload.contractURI,
                        refundable: payload.refundable,
                        allowMint: payload.allowMint
                    };
                    if (payload.reserveless) {
                        if (payload.type === 'DRC721') {
                            result = await decimalEVM.createCollectionDRC721Reserveless(nftParams);
                        } else {
                            result = await decimalEVM.createCollectionDRC1155Reserveless(nftParams);
                        }
                    } else {
                        if (payload.type === 'DRC721') {
                            result = await decimalEVM.createCollectionDRC721(nftParams);
                        } else {
                            result = await decimalEVM.createCollectionDRC1155(nftParams);
                        }
                    }
                    break;

                case 'mint_nft':
                    if (payload.reserveless) {
                        if (payload.type === 'DRC721') {
                            result = await decimalEVM.mintNFT(payload.nftCollectionAddress, payload.to, payload.tokenURI);
                        } else {
                            result = await decimalEVM.mintNFT(payload.nftCollectionAddress, payload.to, payload.tokenURI, payload.tokenId, payload.amount);
                        }
                    } else if (payload.reserveType === 'DEL') {
                        const reserve = decimalEVM.parseEther(payload.reserve);
                        if (payload.type === 'DRC721') {
                            result = await decimalEVM.mintNFTWithDELReserve(payload.nftCollectionAddress, payload.to, payload.tokenURI, reserve);
                        } else {
                            result = await decimalEVM.mintNFTWithDELReserve(payload.nftCollectionAddress, payload.to, payload.tokenURI, reserve, payload.tokenId, payload.amount);
                        }
                    } else {
                        const reserve = decimalEVM.parseEther(payload.reserve);
                        const signMint = payload.sign ? payload.sign : await decimalEVM.getSignPermitToken(payload.tokenAddress, payload.nftCollectionAddress, reserve);
                        if (payload.type === 'DRC721') {
                            result = await decimalEVM.mintNFTWithTokenReserve(payload.nftCollectionAddress, payload.to, payload.tokenURI, reserve, payload.tokenAddress, signMint);
                        } else {
                            result = await decimalEVM.mintNFTWithTokenReserve(payload.nftCollectionAddress, payload.to, payload.tokenURI, reserve, payload.tokenAddress, signMint, payload.tokenId, payload.amount);
                        }
                    }
                    break;

                case 'add_del_reserve_nft':
                    result = await decimalEVM.addDELReserveNFT(payload.nftCollectionAddress, payload.tokenId, decimalEVM.parseEther(payload.reserve));
                    break;

                case 'add_token_reserve_nft':
                    const reserveAdd = decimalEVM.parseEther(payload.reserve);
                    const signAdd = payload.sign ? payload.sign : await decimalEVM.getSignPermitToken(payload.tokenAddress, payload.nftCollectionAddress, reserveAdd);
                    result = await decimalEVM.addTokenReserveNFT(payload.nftCollectionAddress, payload.tokenId, reserveAdd, signAdd);
                    break;

                case 'transfer_nft':
                    if (payload.type === 'DRC721') {
                        result = await decimalEVM.transferNFT(payload.nftCollectionAddress, payload.from, payload.to, payload.tokenId);
                    } else {
                        result = await decimalEVM.transferNFT(payload.nftCollectionAddress, payload.from, payload.to, payload.tokenId, payload.amount);
                    }
                    break;

                case 'transfer_batch_nft1155':
                    result = await decimalEVM.transferBatchNFT1155(payload.nftCollectionAddress, payload.from, payload.to, payload.tokenIds, payload.amounts);
                    break;

                case 'disable_mint_nft':
                    result = await decimalEVM.disableMintNFT(payload.nftCollectionAddress);
                    break;

                case 'burn_nft':
                    if (payload.type === 'DRC721') {
                        result = await decimalEVM.burnNFT(payload.nftCollectionAddress, payload.tokenId);
                    } else {
                        result = await decimalEVM.burnNFT(payload.nftCollectionAddress, payload.tokenId, payload.amount);
                    }
                    break;

                case 'set_token_uri_nft':
                    result = await decimalEVM.setTokenURINFT(payload.nftCollectionAddress, payload.tokenId, payload.tokenURI);
                    break;

                case 'approve_nft721':
                    result = await decimalEVM.approveNFT721(payload.nftCollectionAddress, payload.to, payload.tokenId);
                    break;

                case 'approve_for_all_nft':
                    result = await decimalEVM.approveForAllNFT(payload.nftCollectionAddress, payload.to, payload.approved);
                    break;

                // Delegation Operations
                case 'delegate_del':
                    const amountDelegate = decimalEVM.parseEther(payload.amount);
                    if (payload.days > 0) {
                        const latestBlock = await decimalEVM.getLatestBlock();
                        const holdTimestamp = latestBlock.timestamp + payload.days * 86400;
                        result = await decimalEVM.delegateDELHold(payload.validator, amountDelegate, holdTimestamp);
                    } else {
                        result = await decimalEVM.delegateDEL(payload.validator, amountDelegate);
                    }
                    break;

                case 'delegate_token':
                    const amountToken = decimalEVM.parseEther(payload.amount);
                    const delegationAddress = await decimalEVM.getDecimalContractAddress('delegation');
                    const signDelegate = payload.sign ? payload.sign : await decimalEVM.getSignPermitToken(payload.tokenAddress, delegationAddress, amountToken);
                    if (payload.days > 0) {
                        const latestBlock = await decimalEVM.getLatestBlock();
                        const holdTimestamp = latestBlock.timestamp + payload.days * 86400;
                        result = await decimalEVM.delegateTokenHold(payload.validator, payload.tokenAddress, amountToken, holdTimestamp, signDelegate);
                    } else {
                        result = await decimalEVM.delegateToken(payload.validator, payload.tokenAddress, amountToken, signDelegate);
                    }
                    break;

                case 'delegate_nft':
                    const delegationNftAddress = await decimalEVM.getDecimalContractAddress('delegation-nft');
                    const signDelegateNFT = payload.sign ? payload.sign : payload.type === 'DRC721'
                        ? await decimalEVM.getSignPermitDRC721(payload.nftCollectionAddress, delegationNftAddress, payload.tokenId)
                        : await decimalEVM.getSignPermitDRC1155(payload.nftCollectionAddress, delegationNftAddress);
                    if (payload.type === 'DRC721') {
                        if (payload.days > 0) {
                            const latestBlock = await decimalEVM.getLatestBlock();
                            const holdTimestamp = latestBlock.timestamp + payload.days * 86400;
                            result = await decimalEVM.delegateDRC721Hold(payload.validator, payload.nftCollectionAddress, payload.tokenId, holdTimestamp, signDelegateNFT);
                        } else {
                            result = await decimalEVM.delegateDRC721(payload.validator, payload.nftCollectionAddress, payload.tokenId, signDelegateNFT);
                        }
                    } else {
                        if (payload.days > 0) {
                            const latestBlock = await decimalEVM.getLatestBlock();
                            const holdTimestamp = latestBlock.timestamp + payload.days * 86400;
                            result = await decimalEVM.delegateDRC1155Hold(payload.validator, payload.nftCollectionAddress, payload.tokenId, payload.amount, holdTimestamp, signDelegateNFT);
                        } else {
                            result = await decimalEVM.delegateDRC1155(payload.validator, payload.nftCollectionAddress, payload.tokenId, payload.amount, signDelegateNFT);
                        }
                    }
                    break;

                case 'transfer_stake_token':
                    if (payload.holdTimestamp) {
                        result = await decimalEVM.transferStakeTokenHold(payload.validator, payload.token, decimalEVM.parseEther(payload.amount), payload.holdTimestamp, payload.newValidator);
                    } else {
                        result = await decimalEVM.transferStakeToken(payload.validator, payload.token, decimalEVM.parseEther(payload.amount), payload.newValidator);
                    }
                    break;

                case 'withdraw_stake_token':
                    result = await decimalEVM.withdrawStakeToken(payload.validator, payload.token, decimalEVM.parseEther(payload.amount));
                    break;

                case 'stake_token_to_hold':
                    const latestBlock = await decimalEVM.getLatestBlock();
                    const newHoldTimestamp = latestBlock.timestamp + payload.days * 86400;
                    result = await decimalEVM.stakeTokenToHold(payload.validator, payload.token, decimalEVM.parseEther(payload.amount), payload.oldHoldTimestamp, newHoldTimestamp);
                    break;

                case 'stake_token_reset_hold':
                    result = await decimalEVM.stakeTokenResetHold(payload.validator, payload.delegator, payload.token, payload.holdTimestamp);
                    break;

                case 'stake_token_reset_hold_del':
                    result = await decimalEVM.stakeTokenResetHoldDEL(payload.validator, payload.delegator, payload.holdTimestamp);
                    break;

                case 'withdraw_token_with_reset':
                    result = await decimalEVM.withdrawTokenWithReset(payload.validator, payload.token, decimalEVM.parseEther(payload.amount), payload.holdTimestamps);
                    break;

                case 'transfer_token_with_reset':
                    result = await decimalEVM.transferTokenWithReset(payload.validator, payload.token, decimalEVM.parseEther(payload.amount), payload.newValidator, payload.holdTimestamps);
                    break;

                case 'hold_token_with_reset':
                    const holdLatestBlock = await decimalEVM.getLatestBlock();
                    const newHoldTimestampToken = holdLatestBlock.timestamp + payload.days * 86400;
                    result = await decimalEVM.holdTokenWithReset(payload.validator, payload.token, decimalEVM.parseEther(payload.amount), newHoldTimestampToken, payload.holdTimestamps);
                    break;

                case 'apply_penalty_to_stake_token':
                    result = await decimalEVM.applyPenaltyToStakeToken(payload.validator, payload.delegator, payload.token);
                    break;

                case 'apply_penalties_to_stake_token':
                    result = await decimalEVM.applyPenaltiesToStakeToken(payload.validator, payload.delegator, payload.token);
                    break;

                case 'complete_stake_token':
                    result = await decimalEVM.completeStakeToken(payload.stakeIndexes);
                    break;

                case 'transfer_stake_nft':
                    if (payload.holdTimestamp) {
                        result = await decimalEVM.transferStakeNFTHold(payload.validator, payload.token, payload.tokenId, payload.amount, payload.newValidator, payload.holdTimestamp);
                    } else {
                        result = await decimalEVM.transferStakeNFT(payload.validator, payload.token, payload.tokenId, payload.amount, payload.newValidator);
                    }
                    break;

                case 'withdraw_stake_nft':
                    if (payload.holdTimestamp) {
                        result = await decimalEVM.withdrawStakeNFTHold(payload.validator, payload.token, payload.tokenId, payload.amount, payload.holdTimestamp);
                    } else {
                        result = await decimalEVM.withdrawStakeNFT(payload.validator, payload.token, payload.tokenId, payload.amount);
                    }
                    break;

                case 'stake_nft_to_hold':
                    const nftLatestBlock = await decimalEVM.getLatestBlock();
                    const newHoldTimestampNFT = nftLatestBlock.timestamp + payload.days * 86400;
                    result = await decimalEVM.stakeNFTToHold(payload.validator, payload.token, payload.tokenId, payload.amount, payload.oldHoldTimestamp, newHoldTimestampNFT);
                    break;

                case 'stake_nft_reset_hold':
                    result = await decimalEVM.stakeNFTResetHold(payload.validator, payload.delegator, payload.token, payload.tokenId, payload.holdTimestamp);
                    break;

                case 'withdraw_nft_with_reset':
                    result = await decimalEVM.withdrawNFTWithReset(payload.validator, payload.token, payload.tokenId, payload.amount, payload.holdTimestamps);
                    break;

                case 'transfer_nft_with_reset':
                    result = await decimalEVM.transferNFTWithReset(payload.validator, payload.token, payload.tokenId, payload.amount, payload.newValidator, payload.holdTimestamps);
                    break;

                case 'hold_nft_with_reset':
                    const nftHoldLatestBlock = await decimalEVM.getLatestBlock();
                    const newHoldTimestampNFTHold = nftHoldLatestBlock.timestamp + payload.days * 86400;
                    result = await decimalEVM.holdNFTWithReset(payload.validator, payload.token, payload.tokenId, payload.amount, newHoldTimestampNFTHold, payload.holdTimestamps);
                    break;

                case 'complete_stake_nft':
                    result = await decimalEVM.completeStakeNFT(payload.stakeIndexes);
                    break;

                // Validator Operations
                case 'add_validator_with_del':
                    const validatorParams = {
                        operator_address: tempWallets[payload.wallet_id].evmAddress,
                        reward_address: payload.reward_address,
                        consensus_pubkey: Buffer.from(tempWallets[payload.wallet_id].getPublicKey().key.buffer).toString('base64'),
                        description: payload.description,
                        commission: payload.commission
                    };
                    result = await decimalEVM.addValidatorWithETH(validatorParams, decimalEVM.parseEther(payload.amount));
                    break;

                case 'add_validator_with_token':
                    const validatorTokenParams = {
                        operator_address: tempWallets[payload.wallet_id].evmAddress,
                        reward_address: payload.reward_address,
                        consensus_pubkey: Buffer.from(tempWallets[payload.wallet_id].getPublicKey().key.buffer).toString('base64'),
                        description: payload.description,
                        commission: payload.commission
                    };
                    const stakeValidator = {
                        token: payload.tokenAddress,
                        amount: decimalEVM.parseEther(payload.amount)
                    };
                    const masterValidatorAddress = await decimalEVM.getDecimalContractAddress('master-validator');
                    const signValidator = payload.sign ? payload.sign : await decimalEVM.getSignPermitToken(payload.tokenAddress, masterValidatorAddress, stakeValidator.amount);
                    result = await decimalEVM.addValidatorWithToken(validatorTokenParams, stakeValidator, signValidator);
                    break;

                case 'pause_validator':
                    result = await decimalEVM.pauseValidator(payload.validator);
                    break;

                case 'unpause_validator':
                    result = await decimalEVM.unpauseValidator(payload.validator);
                    break;

                case 'update_validator_meta':
                    const validatorMeta = {
                        operator_address: tempWallets[payload.wallet_id].evmAddress,
                        reward_address: payload.reward_address,
                        consensus_pubkey: Buffer.from(tempWallets[payload.wallet_id].getPublicKey().key.buffer).toString('base64'),
                        description: payload.description,
                        commission: payload.commission
                    };
                    result = await decimalEVM.updateValidatorMeta(validatorMeta);
                    break;

                // Multicall Operations
                case 'multi_send_token':
                    result = await decimalEVM.multiSendToken(payload.data, payload.memo);
                    break;

                case 'multi_call':
                    result = await decimalEVM.multiCall(payload.callDatas);
                    break;

                // MultiSig Operations
                case 'create_multisig':
                    result = await decimalEVM.multisig.create(payload.ownerData, payload.weightThreshold);
                    break;

                case 'build_tx_send_del':
                    result = await decimalEVM.multisig.buildTxSendDEL(payload.multisigAddress, payload.to, decimalEVM.parseEther(payload.amount));
                    break;

                case 'build_tx_send_token':
                    result = await decimalEVM.multisig.buildTxSendToken(payload.multisigAddress, payload.tokenAddress, payload.to, decimalEVM.parseEther(payload.amount));
                    break;

                case 'build_tx_send_nft':
                    if (payload.type === 'DRC721') {
                        result = await decimalEVM.multisig.buildTxSendNFT(payload.multisigAddress, payload.tokenAddress, payload.to, payload.tokenId);
                    } else {
                        result = await decimalEVM.multisig.buildTxSendNFT(payload.multisigAddress, payload.tokenAddress, payload.to, payload.tokenId, payload.amount);
                    }
                    break;

                case 'sign_multisig_tx':
                    result = await decimalEVM.multisig.signTx(payload.multisigAddress, payload.safeTx);
                    break;

                case 'approve_hash_multisig':
                    result = await decimalEVM.multisig.approveHash(payload.multisigAddress, payload.safeTx);
                    break;

                case 'execute_multisig_tx':
                    result = await decimalEVM.multisig.executeTx(payload.multisigAddress, payload.safeTx, payload.signatures);
                    break;

                case 'get_current_approve_transactions':
                    result = await decimalEVM.multisig.getCurrentApproveTransactions(payload.multisigAddress);
                    break;

                case 'get_expired_approve_transactions':
                    result = await decimalEVM.multisig.getExpiredApproveTransactions(payload.multisigAddress);
                    break;

                // Bridge Operations
                case 'bridge_transfer_native':
                    const serviceFee = await decimalEVM.getBridgeServiceFees(payload.toChainId);
                    result = await decimalEVM.bridgeTransferNative(
                        payload.to,
                        decimalEVM.parseEther(payload.amount),
                        serviceFee,
                        payload.fromChainId,
                        payload.toChainId
                    );
                    break;

                case 'bridge_transfer_tokens':
                    const bridgeAddress = await decimalEVM.getDecimalContractAddress('bridge');
                    await decimalEVM.approveToken(payload.tokenAddress, bridgeAddress, decimalEVM.parseEther(payload.amount));
                    const serviceFeeTokens = await decimalEVM.getBridgeServiceFees(payload.toChainId);
                    result = await decimalEVM.bridgeTransferTokens(
                        payload.tokenAddress,
                        payload.to,
                        decimalEVM.parseEther(payload.amount),
                        serviceFeeTokens,
                        payload.fromChainId,
                        payload.toChainId
                    );
                    break;

                case 'bridge_complete_transfer':
                    result = await decimalEVM.bridgeCompleteTransfer(payload.toChainId, payload.encodedVM, payload.unwrapWETH);
                    break;

                // Checks Operations
                case 'create_checks_del':
                    const latestBlockChecks = await decimalEVM.getLatestBlock();
                    const dueBlock = latestBlockChecks.number + payload.blockOffset;
                    const amountWei = decimalEVM.parseEther(payload.amount);
                    const totalAmount = decimalEVM.parseEther(payload.passwords.length * payload.amount);
                    result = await decimalEVM.createChecksDEL(payload.passwords, amountWei, dueBlock);
                    result.totalAmount = totalAmount.toString();
                    break;

                case 'create_checks_token':
                    const latestBlockTokenChecks = await decimalEVM.getLatestBlock();
                    const dueBlockToken = latestBlockTokenChecks.number + payload.blockOffset;
                    const amountWeiToken = decimalEVM.parseEther(payload.amount);
                    const totalAmountToken = decimalEVM.parseEther(payload.passwords.length * payload.amount);
                    const checksAddress = await decimalEVM.getDecimalContractAddress('checks');
                    const signChecks = payload.sign ? payload.sign : await decimalEVM.getSignPermitToken(payload.tokenAddress, checksAddress, totalAmountToken);
                    result = await decimalEVM.createChecksToken(payload.passwords, amountWeiToken, dueBlockToken, payload.tokenAddress, signChecks);
                    result.totalAmount = totalAmountToken.toString();
                    break;

                case 'redeem_checks':
                    result = await decimalEVM.redeemChecks(payload.passwords, payload.checks);
                    break;

                // Viewing Functions
                case 'get_balance':
                    result = { balance: decimalEVM.formatEther(await decimalEVM.getBalance(payload.address)) };
                    break;

                case 'get_balance_eth':
                    result = { balance: decimalEVM.formatEther(await decimalEVM.getBalanceETH(payload.address)) };
                    break;

                case 'get_balance_bnb':
                    result = { balance: decimalEVM.formatEther(await decimalEVM.getBalanceBNB(payload.address)) };
                    break;

                case 'check_token_exists':
                    result = await decimalEVM.checkTokenExists(payload.tokenAddress);
                    break;

                case 'get_address_token_by_symbol':
                    result = await decimalEVM.getAddressTokenBySymbol(payload.symbol);
                    break;

                case 'get_commission_symbol':
                    result = await decimalEVM.getCommissionSymbol(payload.symbol);
                    break;

                case 'calculate_buy_output':
                    result = await decimalEVM.calculateBuyOutput(payload.tokenAddress, decimalEVM.parseEther(payload.amountDel));
                    break;

                case 'calculate_buy_input':
                    result = await decimalEVM.calculateBuyInput(payload.tokenAddress, decimalEVM.parseEther(payload.amountTokens));
                    break;

                case 'calculate_sell_input':
                    result = await decimalEVM.calculateSellInput(payload.tokenAddress, decimalEVM.parseEther(payload.amountDEL));
                    break;

                case 'calculate_sell_output':
                    result = await decimalEVM.calculateSellOutput(payload.tokenAddress, decimalEVM.parseEther(payload.amountTokens));
                    break;

                case 'get_sign_permit_token':
                    result = await decimalEVM.getSignPermitToken(payload.tokenAddress, payload.spender, decimalEVM.parseEther(payload.amount));
                    break;

                case 'allowance_token':
                    result = await decimalEVM.allowanceToken(payload.tokenAddress, payload.owner, payload.spender);
                    break;

                case 'balance_of_token':
                    result = await decimalEVM.balanceOfToken(payload.tokenAddress, payload.account);
                    break;

                case 'supports_interface_token':
                    result = await decimalEVM.supportsInterfaceToken(payload.tokenAddress, payload.interfaceId);
                    break;

                case 'get_nft_type':
                    result = await decimalEVM.getNftType(payload.nftCollectionAddress);
                    break;

                case 'get_nft_type_from_contract':
                    result = await decimalEVM.getNftTypeFromContract(payload.nftCollectionAddress);
                    break;

                case 'get_approved_nft721':
                    result = await decimalEVM.getApprovedNFT721(payload.nftCollectionAddress, payload.tokenId);
                    break;

                case 'is_approved_for_all_nft':
                    result = await decimalEVM.isApprovedForAllNFT(payload.nftCollectionAddress, payload.owner, payload.spender);
                    break;

                case 'owner_of_nft721':
                    result = await decimalEVM.ownerOfNFT721(payload.nftCollectionAddress, payload.tokenId);
                    break;

                case 'get_token_uri_nft':
                    result = await decimalEVM.getTokenURINFT(payload.nftCollectionAddress, payload.tokenId);
                    break;

                case 'get_allow_mint_nft':
                    result = await decimalEVM.getAllowMintNFT(payload.nftCollectionAddress);
                    break;

                case 'balance_of_nft':
                    if (payload.type === 'DRC721') {
                        result = await decimalEVM.balanceOfNFT(payload.nftCollectionAddress, payload.account);
                    } else {
                        result = await decimalEVM.balanceOfNFT(payload.nftCollectionAddress, payload.account, payload.tokenId);
                    }
                    break;

                case 'supports_interface_nft':
                    result = await decimalEVM.supportsInterfaceNFT(payload.nftCollectionAddress, payload.interfaceId);
                    break;

                case 'get_rate_nft1155':
                    result = await decimalEVM.getRateNFT1155(payload.nftCollectionAddress, payload.tokenId);
                    break;

                case 'calc_reserve_nft1155':
                    result = await decimalEVM.calcReserveNFT1155(payload.nftCollectionAddress, payload.tokenId, payload.quantity);
                    break;

                case 'get_sign_permit_nft':
                    if (payload.type === 'DRC721') {
                        result = await decimalEVM.getSignPermitDRC721(payload.nftCollectionAddress, payload.spender, payload.tokenId);
                    } else {
                        result = await decimalEVM.getSignPermitDRC1155(payload.nftCollectionAddress, payload.spender);
                    }
                    break;

                case 'get_reserve_nft':
                    result = await decimalEVM.getReserveNFT(payload.nftCollectionAddress, payload.tokenId);
                    break;

                case 'get_refundable_nft':
                    result = await decimalEVM.getRefundableNFT(payload.nftCollectionAddress);
                    break;

                case 'get_supply_nft1155':
                    result = await decimalEVM.getSupplyNFT1155(payload.nftCollectionAddress, payload.tokenId);
                    break;

                case 'get_token_stakes_page_by_member':
                    result = await decimalEVM.getTokenStakesPageByMember(payload.account, payload.size, payload.offset);
                    break;

                case 'get_frozen_stakes_queue_token':
                    result = await decimalEVM.getFrozenStakesQueueToken();
                    break;

                case 'get_freeze_time_token':
                    result = await decimalEVM.getFreezeTimeToken();
                    break;

                case 'get_stake_token':
                    result = await decimalEVM.getStakeToken(payload.validator, payload.delegator, payload.tokenAddress);
                    break;

                case 'get_stake_id_token':
                    result = await decimalEVM.getStakeIdToken(payload.validator, payload.delegator, payload.tokenAddress);
                    break;

                case 'get_nft_stakes_page_by_member':
                    result = await decimalEVM.getNFTStakesPageByMember(payload.account, payload.size, payload.offset);
                    break;

                case 'get_frozen_stakes_queue_nft':
                    result = await decimalEVM.getFrozenStakesQueueNFT();
                    break;

                case 'get_freeze_time_nft':
                    result = await decimalEVM.getFreezeTimeNFT();
                    break;

                case 'get_validator_status':
                    result = await decimalEVM.getValidatorStatus(payload.validator);
                    break;

                case 'validator_is_active':
                    result = await decimalEVM.validatorIsActive(payload.validator);
                    break;

                case 'validator_is_member':
                    result = await decimalEVM.validatorIsMember(payload.validator);
                    break;

                // Subgraph Operations
                case 'get_decimal_contracts':
                    result = await subgraph.getDecimalContracts();
                    break;

                case 'get_validators':
                    result = await subgraph.getValidators();
                    break;

                case 'get_validator':
                    result = await subgraph.getValidator(payload.validator);
                    break;

                case 'get_validator_penalties':
                    result = await subgraph.getValidatorPenalties(payload.validator, payload.first, payload.skip);
                    break;

                case 'get_validator_penalties_from_block':
                    result = await subgraph.getValidatorPenaltiesFromBlock(payload.validator, payload.blockNumber, payload.first, payload.skip);
                    break;

                case 'get_sum_amount_to_penalty':
                    result = await subgraph.getSumAmountToPenalty();
                    break;

                case 'get_tokens':
                    result = await subgraph.getTokens(payload.first, payload.skip);
                    break;

                case 'get_tokens_by_owner':
                    result = await subgraph.getTokensByOwner(payload.owner, payload.first, payload.skip);
                    break;

                case 'get_token_by_symbol':
                    result = await subgraph.getTokenBySymbol(payload.symbol);
                    break;

                case 'get_token_by_address':
                    result = await subgraph.getTokenByAddress(payload.tokenAddress);
                    break;

                case 'get_address_balances':
                    result = await subgraph.getAddressBalances(payload.account, payload.first, payload.skip);
                    break;

                case 'get_stakes':
                    result = await subgraph.getStakes(payload.first, payload.skip);
                    break;

                case 'get_stakes_by_address':
                    result = await subgraph.getStakesByAddress(payload.delegator, payload.first, payload.skip);
                    break;

                case 'get_stakes_by_validator':
                    result = await subgraph.getStakesByValidotor(payload.validator, payload.first, payload.skip);
                    break;

                case 'get_transfer_stakes':
                    result = await subgraph.getTransferStakes(payload.first, payload.skip);
                    break;

                case 'get_transfer_stakes_by_address':
                    result = await subgraph.getTransferStakesByAddress(payload.delegator, payload.first, payload.skip);
                    break;

                case 'get_withdraw_stakes':
                    result = await subgraph.getWithdrawStakes(payload.first, payload.skip);
                    break;

                case 'get_withdraw_stakes_by_address':
                    result = await subgraph.getWithdrawStakesByAddress(payload.delegator, payload.first, payload.skip);
                    break;

                case 'get_nft_collections':
                    result = await subgraph.getNftCollections(payload.first, payload.skip);
                    break;

                case 'get_nft_collections_by_creator':
                    result = await subgraph.getNftCollectionsByCreator(payload.owner, payload.first, payload.skip);
                    break;

                case 'get_nft_collection_by_address':
                    result = await subgraph.getNftCollectionByAddress(payload.nftCollectionAddress);
                    break;

                case 'get_nft_collection_type':
                    result = await subgraph.getNftCollectionType(payload.nftCollectionAddress);
                    break;

                case 'get_nfts':
                    result = await subgraph.getNfts(payload.first, payload.skip);
                    break;

                case 'get_nfts_by_collection':
                    result = await subgraph.getNftsByCollection(payload.nftCollectionAddress, payload.first, payload.skip);
                    break;

                case 'get_address_balances_nfts':
                    result = await subgraph.getAddressBalancesNfts(payload.account, payload.first, payload.skip);
                    break;

                case 'get_address_balances_nfts_by_collection':
                    result = await subgraph.getAddressBalancesNftsByCollection(payload.account, payload.nftCollectionAddress, payload.first, payload.skip);
                    break;

                case 'get_nft_by_collection_and_token_id':
                    result = await subgraph.getNftByCollectionAndTokenId(payload.nftCollectionAddress, payload.tokenId);
                    break;

                case 'get_nft_stakes':
                    result = await subgraph.getNFTStakes(payload.first, payload.skip);
                    break;

                case 'get_nft_stakes_by_address':
                    result = await subgraph.getNFTStakesByAddress(payload.account, payload.first, payload.skip);
                    break;

                case 'get_nft_stakes_by_validator':
                    result = await subgraph.getNFTStakesByValidotor(payload.validator, payload.first, payload.skip);
                    break;

                case 'get_transfer_nft_stakes':
                    result = await subgraph.getTransferNFTStakes(payload.first, payload.skip);
                    break;

                case 'get_transfer_nft_stakes_by_address':
                    result = await subgraph.getTransferNFTStakesByAddress(payload.account, payload.first, payload.skip);
                    break;

                case 'get_withdraw_nft_stakes':
                    result = await subgraph.getWithdrawNFTStakes(payload.first, payload.skip);
                    break;

                case 'get_withdraw_nft_stakes_by_address':
                    result = await subgraph.getWithdrawNFTStakesByAddress(payload.account, payload.first, payload.skip);
                    break;

                case 'get_bridge_tokens':
                    result = await subgraph.getBridgeTokens(payload.first, payload.skip);
                    break;

                case 'get_bridge_token_by_address':
                    result = await subgraph.getBridgeTokenByAddress(payload.address);
                    break;

                case 'get_bridge_token_by_symbol':
                    result = await subgraph.getBridgeTokenBySymbol(payload.symbol);
                    break;

                case 'get_bridge_transfers':
                    result = await subgraph.getBridgeTransfers(payload.first, payload.skip);
                    break;

                case 'get_bridge_transfers_by_from':
                    result = await subgraph.getBridgeTransfersByFrom(payload.address, payload.first, payload.skip);
                    break;

                case 'get_bridge_transfers_by_to':
                    result = await subgraph.getBridgeTransfersByTo(payload.address, payload.first, payload.skip);
                    break;

                case 'get_bridge_transfers_by_token':
                    result = await subgraph.getBridgeTransfersByToken(payload.address, payload.first, payload.skip);
                    break;

                case 'get_multisig_wallets':
                    result = await subgraph.getMultisigWallets(payload.first, payload.skip);
                    break;

                case 'get_multisig_wallets_by_participant':
                    result = await subgraph.getMultisigWalletsByParticipant(payload.participant, payload.first, payload.skip);
                    break;

                case 'get_multisig_approve_transactions':
                    result = await subgraph.getMultisigApproveTransactionsByMultisigAddressAndNonce(payload.addressMultisig, payload.nonce, payload.first, payload.skip);
                    break;

                case 'get_multisig_expired_approve_transactions':
                    result = await subgraph.getMultisigApproveTransactionsByMultisigAddressAndNonceNot(payload.addressMultisig, payload.nonce, payload.first, payload.skip);
                    break;

                // IPFS Operations
                case 'upload_token_buffer_to_ipfs':
                    const bufferToken = Buffer.from(payload.buffer, 'base64');
                    result = await decimalEVM.uploadTokenBufferToIPFS(bufferToken, payload.filename);
                    break;

                case 'upload_nft_buffer_to_ipfs':
                    const bufferNFT = Buffer.from(payload.buffer, 'base64');
                    result = await decimalEVM.uploadNFTBufferToIPFS(bufferNFT, payload.filename, payload.name, payload.description);
                    break;

                case 'get_url_from_cid':
                    result = decimalEVM.getUrlFromCid(payload.cid);
                    break;

                // Helper Functions
                case 'parse_ether':
                    result = decimalEVM.parseEther(payload.amount).toString();
                    break;

                case 'format_ether':
                    result = decimalEVM.formatEther(payload.amountWei);
                    break;

                case 'get_address':
                    result = decimalEVM.getAddress(payload.address);
                    break;

                case 'get_latest_block':
                    result = await decimalEVM.getLatestBlock();
                    break;

                case 'get_fee_data':
                    result = await decimalEVM.getFeeData();
                    break;

                // Contract Operations
                case 'verify_contract':
                    result = await decimalEVM.verifyСontract(
                        payload.contractAddress,
                        payload.contractCode,
                        payload.compiler,
                        payload.optimizer,
                        payload.runs,
                        payload.evm_version
                    );
                    break;

                case 'call_contract':
                    const contract = await decimalEVM.connectToContract(payload.contractAddress);
                    result = await contract.call(payload.method, payload.params);
                    break;

                case 'call_write_contract':
                    const writeContract = await decimalEVM.connectToContract(payload.contractAddress);
                    const options = payload.options ? payload.options : await writeContract.getDefaultOptions();
                    result = await writeContract.call(payload.method, payload.params, options);
                    break;

                case 'send_signed_transaction':
                    const signedContract = await decimalEVM.connectToContract(payload.contractAddress);
                    const signedOptions = payload.options ? payload.options : await signedContract.getDefaultOptions();
                    const populateTransaction = await signedContract.populateTransaction(payload.method, payload.params, signedOptions);
                    populateTransaction.chainId = payload.chainId || 20202020;
                    const signTransaction = await signedContract.signTransaction(populateTransaction);
                    result = await signedContract.sendSignedTransaction(signTransaction);
                    break;

                // Check Wallet
                case 'is_wallet_registered':
                    result = {
                        success: true,
                        registered: !!tempWallets[payload.wallet_id],
                        message: tempWallets[payload.wallet_id]
                            ? `Кошелёк "${payload.wallet_id}" существует`
                            : `Кошелёк "${payload.wallet_id}" не зарегистрирован`
                    };
                    break;

                default:
                    throw new Error(`Неизвестное действие: ${action}`);
            }

            socket.write(JSON.stringify({ success: true, result }));
        } catch (err) {
            console.error('❌ Ошибка в обработке запроса:', err.message);
            socket.write(JSON.stringify({ success: false, error: err.message }));
        }
    });

    socket.on('end', () => {
        console.log('🔌 Клиент отключён');
    });
});

// Расчет комиссии для создания токена
function calculateTokenCommission(symbol) {
    const length = symbol.length;
    if (length === 3) return 2500000;
    if (length === 4) return 250000;
    if (length === 5) return 25000;
    if (length === 6) return 2500;
    return 250; // 7-10 букв
}

server.listen(SOCKET_PATH, () => {
    fs.chmodSync(SOCKET_PATH, '700');
    console.log(`⚙️ IPC-сервер запущен по пути: ${SOCKET_PATH}`);
});