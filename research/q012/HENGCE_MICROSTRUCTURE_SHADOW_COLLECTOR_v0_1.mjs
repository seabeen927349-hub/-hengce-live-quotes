import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import { WebSocketClient } from '@fugle/marketdata';

const API_KEY = process.env.FUGLE_API_KEY;
const SYMBOLS = (process.env.HENGCE_SYMBOLS || '').split(',').map(s => s.trim()).filter(Boolean);
const OUT_ROOT = process.env.HENGCE_MICRO_OUT || './hengce_microstructure';

if (!API_KEY) throw new Error('FUGLE_API_KEY is required');
if (!SYMBOLS.length) throw new Error('HENGCE_SYMBOLS is required, comma-separated');

function taipeiDateFromMicros(us) {
  const d = new Date(Math.floor(us / 1000));
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Taipei', year:'numeric', month:'2-digit', day:'2-digit' }).format(d);
}

function appendRecord(channel, payload) {
  const date = taipeiDateFromMicros(payload.time || Date.now()*1000);
  const dir = path.join(OUT_ROOT, 'raw', date);
  fs.mkdirSync(dir, { recursive: true });
  const symbol = payload.symbol || 'UNKNOWN';
  const record = {
    capturedAt: new Date().toISOString(),
    source: 'FugleMarketData',
    channel,
    symbol,
    validContinuous: payload.isContinuous !== false && payload.isTrial !== true,
    payload,
  };
  const canonical = JSON.stringify(record);
  record.payloadHash = crypto.createHash('sha256').update(canonical).digest('hex');
  fs.appendFileSync(path.join(dir, `${symbol}.${channel}.ndjson`), JSON.stringify(record) + '\n');
}

const client = new WebSocketClient({ apiKey: API_KEY });
const stock = client.stock;

stock.on('message', (message) => {
  try {
    const msg = JSON.parse(message);
    if (msg?.event !== 'data' || !msg?.data || !msg?.channel) return;
    if (msg.channel !== 'books' && msg.channel !== 'trades') return;
    appendRecord(msg.channel, msg.data);
  } catch (err) {
    console.error('[parse/write error]', err);
  }
});
stock.on('error', (err) => console.error('[fugle error]', err));
stock.on('disconnect', (code, msg) => console.error('[disconnect]', code, msg));

await stock.connect();
for (const symbol of SYMBOLS) {
  stock.subscribe({ channel: 'books', symbol });
  stock.subscribe({ channel: 'trades', symbol });
}
console.log(JSON.stringify({status:'RUNNING', symbols:SYMBOLS, channels:['books','trades'], out:OUT_ROOT}));
