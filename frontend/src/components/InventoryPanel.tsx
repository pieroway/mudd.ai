export interface ClientState {
  room_id: string
  room_name: string
  inventory: { id: string; name: string }[]
}

// Socket JSON is untrusted at runtime, even when TypeScript types match the server.
export function isClientState(value: unknown): value is ClientState {
  if (!value || typeof value !== 'object') return false
  const state = value as Partial<ClientState>
  return typeof state.room_id === 'string' && typeof state.room_name === 'string'
    && Array.isArray(state.inventory) && state.inventory.every(item =>
      item && typeof item.id === 'string' && typeof item.name === 'string')
}

export default function InventoryPanel({ state, connected }: {
  state?: ClientState; connected: boolean
}) {
  return (
    <aside id="inventory-panel" className="context-panel" aria-labelledby="inventory-heading" data-testid="inventory-panel">
      <p className="eyebrow">Your belongings</p>
      <h3 id="inventory-heading">Inventory</h3>
      {!connected ? <p role="status">Disconnected. Reconnect to refresh your inventory.</p>
        : !state ? <p role="status">Waiting for inventory…</p>
        : state.inventory.length === 0 ? <p>Your inventory is empty.</p>
        : <ul>{state.inventory.map(item => <li key={item.id}>{item.name}</li>)}</ul>}
      <p className="panel-hint">Use take, drop, or give in the command prompt.</p>
    </aside>
  )
}
