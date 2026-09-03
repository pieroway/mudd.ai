import ws from 'k6/ws';
import { check } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';

const commandLatency = new Trend('command_latency', true);
const commandFailures = new Rate('command_failures');
const commandsSent = new Counter('commands_sent');
const messagesReceived = new Counter('messages_received');

const vus = Number.parseInt(__ENV.LOAD_VUS || '25', 10);
const sessionSeconds = Number.parseInt(__ENV.SESSION_SECONDS || '45', 10);
const thinkTimeMs = Number.parseInt(__ENV.THINK_TIME_MS || '1000', 10);
const commandP95Ms = Number.parseInt(__ENV.COMMAND_P95_MS || '500', 10);
const commandP99Ms = Number.parseInt(__ENV.COMMAND_P99_MS || '1000', 10);

export const options = {
  vus,
  duration: __ENV.LOAD_DURATION || '1m',
  thresholds: {
    checks: ['rate>0.99'],
    command_failures: ['rate<0.01'],
    command_latency: [`p(95)<${commandP95Ms}`, `p(99)<${commandP99Ms}`],
    ws_connecting: ['p(95)<1000'],
  },
};

const commands = [
  { text: 'look', response: /^(Town Square|Forest)/ },
  { text: 'inventory', response: /^Inventory:/ },
  { text: 'north', response: /^You move north\./ },
  { text: 'look', response: /^Forest/ },
  { text: 'south', response: /^You move south\./ },
];

export default function () {
  const runId = (__ENV.RUN_ID || 'local').replace(/[^a-zA-Z0-9-]/g, '');
  const username = `load-${runId}-${__VU}-${__ITER}`.slice(0, 50);
  const url = `${__ENV.WS_URL || 'ws://localhost:18001/ws'}?username=${username}`;

  const response = ws.connect(url, {}, (socket) => {
    let commandIndex = 0;
    let pending = null;
    let welcomed = false;

    socket.on('open', () => {
      socket.setInterval(() => {
        if (!welcomed || pending !== null) {
          return;
        }
        const command = commands[commandIndex % commands.length];
        pending = { ...command, sentAt: Date.now() };
        socket.send(command.text);
        commandsSent.add(1);
        commandIndex += 1;
      }, thinkTimeMs);
    });

    socket.on('message', (rawMessage) => {
      messagesReceived.add(1);
      let message;
      try {
        message = JSON.parse(rawMessage);
      } catch (_) {
        commandFailures.add(true);
        return;
      }

      if (message.type === 'system') {
        welcomed = true;
        return;
      }
      if (message.type === 'error') {
        commandFailures.add(true);
        pending = null;
        return;
      }
      if (pending !== null && pending.response.test(message.text || '')) {
        commandLatency.add(Date.now() - pending.sentAt);
        commandFailures.add(message.success !== true);
        pending = null;
      }
    });

    socket.setTimeout(() => socket.close(), sessionSeconds * 1000);
  });

  check(response, {
    'WebSocket upgraded successfully': (result) => result && result.status === 101,
  });
}
