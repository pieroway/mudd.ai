import type { MapState } from './MapPanel'

export interface ItemView {
  id: string
  name: string
  description?: string
  quantity?: number
  location?: string
  visible_state?: string[]
  actions?: string[]
  contents?: ItemView[]
}

export interface ClientState {
  room_id: string
  room_name: string
  inventory: ItemView[]
  visible_objects?: ItemView[]
  map?: MapState
}

function isItemView(value: unknown, depth = 0): value is ItemView {
  if (!value || typeof value !== 'object' || depth > 8) return false
  const item = value as Partial<ItemView>
  return typeof item.id === 'string' && typeof item.name === 'string'
    && (item.description === undefined || typeof item.description === 'string')
    && (item.quantity === undefined || Number.isInteger(item.quantity) && item.quantity > 0)
    && (item.location === undefined || typeof item.location === 'string')
    && [item.visible_state, item.actions].every(values => values === undefined
      || Array.isArray(values) && values.every(value => typeof value === 'string'))
    && (item.contents === undefined || Array.isArray(item.contents)
      && item.contents.every(child => isItemView(child, depth + 1)))
}

// Socket JSON is untrusted at runtime, even when TypeScript types match the server.
export function isClientState(value: unknown): value is ClientState {
  if (!value || typeof value !== 'object') return false
  const state = value as Partial<ClientState>
  return typeof state.room_id === 'string' && typeof state.room_name === 'string'
    && Array.isArray(state.inventory) && state.inventory.every(item => isItemView(item))
    && (state.visible_objects === undefined || Array.isArray(state.visible_objects)
      && state.visible_objects.every(item => isItemView(item)))
}

function ItemList({ items }: { items: ItemView[] }) {
  return <ul>{items.map(item => <li key={item.id} title={item.actions?.join(', ')}>
    {item.quantity && item.quantity > 1 ? `${item.quantity} × ` : ''}{item.name}
    {inventoryDetails(item)}
    {Boolean(item.contents?.length) && <ItemList items={item.contents!} />}
  </li>)}</ul>
}

function inventoryDetails(item: ItemView): string {
  const location = item.location && ![
    'inventory', 'room', 'contained_in', 'resting_on', 'hidden_under', 'attached_to',
  ].includes(item.location) ? item.location.replace(/_/g, ' ') : undefined
  const details = [location, ...(item.visible_state ?? [])].filter(Boolean)
  return details.length ? ` (${details.join(', ')})` : ''
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
        : <><p>You are carrying the following items...</p><ItemList items={state.inventory} /></>}
      <p className="panel-hint">Use take, drop, or give in the command prompt.</p>
    </aside>
  )
}
