export function apiUrl(path: string): URL {
  const url = new URL(import.meta.env.VITE_API_URL ?? `http://${window.location.hostname}:8000`)
  if (url.hostname === 'localhost' && window.location.hostname !== 'localhost') {
    url.hostname = window.location.hostname
  }
  url.pathname = path
  url.search = ''
  return url
}

export async function authRequest(path: string, body?: object) {
  const response = await fetch(apiUrl(path), {
    method: body ? 'POST' : 'GET',
    credentials: 'include',
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!response.ok) {
    const error = await response.json()
    throw new Error(typeof error.detail === 'string' ? error.detail : 'Authentication failed.')
  }
  return response.status === 204 ? null : response.json()
}
