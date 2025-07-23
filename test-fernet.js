const path = require('path');
const fernet = require(path.resolve(__dirname, 'dsc-js-sdk', 'node_modules', 'fernet'));
require(path.resolve(__dirname, 'dsc-js-sdk', 'node_modules', 'dotenv')).config();

const ENCRYPTION_KEY = process.env.ENCRYPTION_KEY;
if (!ENCRYPTION_KEY) throw new Error('ENCRYPTION_KEY не установлен в .env');

try {
    const decodedKey = Buffer.from(ENCRYPTION_KEY, 'base64');
    if (decodedKey.length !== 32) {
        throw new Error('ENCRYPTION_KEY должен быть 32-байтной строкой в формате base64');
    }
    const secret = new fernet.Secret(ENCRYPTION_KEY);
    const token = new fernet.Token({ secret });
    console.log('ENCRYPTION_KEY действителен для Fernet');
} catch (e) {
    console.error('Недействительный ENCRYPTION_KEY:', e.message);
}
