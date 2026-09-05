import http from 'k6/http';
import { check } from 'k6';

export function authenticatePlayer(wsUrl, username) {
  const url = wsUrl.replace(/^ws/, 'http').replace(/\/ws.*$/, '/auth/register');
  const response = http.post(url, JSON.stringify({
    username, password: 'A long load-test passphrase1!',
  }), { headers: { 'Content-Type': 'application/json', Origin: 'http://localhost:5173' } });
  if (!check(response, { 'Account registration succeeded': result => result.status === 201 })) {
    throw new Error('Load-test registration failed');
  }
  return { headers: { Cookie: `mud_session=${response.cookies.mud_session[0].value}` } };
}
