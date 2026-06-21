/* eslint-disable */
// Throwaway mock backend for testing the Quietcare CLIENT in isolation.
// This is NOT the real server (no agents, Deepgram, Twilio, Redis). It only
// speaks enough of protocol v1 to exercise the client end-to-end.
//
// Run: npm run mock   (from /client)  ->  ws://<host>:8080/ws

const http = require('http');
const fs = require('fs');
const path = require('path');
const { WebSocketServer } = require('ws');

const PORT = process.env.PORT ? Number(process.env.PORT) : 8080;

// Reuse the bundled sample tone as the "speak" audio so we don't ship a second clip.
function loadSampleAudioB64() {
  try {
    const tsPath = path.join(__dirname, '..', 'src', 'assets', 'sampleAudio.ts');
    const src = fs.readFileSync(tsPath, 'utf8');
    const match = src.match(/SAMPLE_AUDIO_B64 = '([^']+)'/);
    return match ? match[1] : '';
  } catch (err) {
    console.warn('Could not load sample audio:', err.message);
    return '';
  }
}

const SPEAK_AUDIO_B64 = loadSampleAudioB64();

const server = http.createServer();
const wss = new WebSocketServer({ server, path: '/ws' });

let promptCounter = 0;

function send(ws, obj) {
  const json = JSON.stringify(obj);
  ws.send(json);
  console.log('  -> sent', summarize(obj));
}

function summarize(obj) {
  const clone = { ...obj };
  for (const k of ['audio_b64', 'audio_clip_b64', 'frame_b64']) {
    if (clone[k] != null) clone[k] = `<${String(clone[k]).length} b64 chars>`;
  }
  return JSON.stringify(clone);
}

wss.on('connection', (ws) => {
  console.log('client connected');

  ws.on('message', (data) => {
    let msg;
    try {
      msg = JSON.parse(data.toString());
    } catch {
      console.log('  <- bad JSON');
      return;
    }
    console.log('  <- recv', summarize(msg));

    switch (msg.type) {
      case 'register':
        console.log(`registered elder: ${msg.elder_id}`);
        send(ws, { type: 'status', state: 'idle' });
        break;

      case 'heartbeat':
        // No-op; just observe.
        break;

      case 'trigger': {
        send(ws, { type: 'ack', received: 'trigger' });
        send(ws, { type: 'status', state: 'checking_in' });

        const prompt_id = `p${++promptCounter}`;
        // A check-in is always: speak, then listen.
        send(ws, {
          type: 'speak',
          prompt_id,
          audio_b64: SPEAK_AUDIO_B64,
          text: 'Margaret, are you okay?',
        });
        setTimeout(() => {
          send(ws, { type: 'listen', prompt_id, duration_ms: 4000 });
        }, 1500);
        break;
      }

      case 'audio_response': {
        const bytes = msg.audio_clip_b64 ? msg.audio_clip_b64.length : 0;
        console.log(
          `received audio_response for ${msg.prompt_id} (${bytes} b64 chars)`,
        );
        send(ws, { type: 'status', state: 'resolved' });
        setTimeout(() => send(ws, { type: 'status', state: 'idle' }), 1500);
        break;
      }

      default:
        console.log('  (unhandled type)', msg.type);
    }
  });

  ws.on('close', () => console.log('client disconnected'));
});

server.listen(PORT, () => {
  console.log(`Quietcare MOCK backend listening on ws://0.0.0.0:${PORT}/ws`);
  console.log('(throwaway test harness — not the real server)');
});
