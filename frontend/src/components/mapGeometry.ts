export interface Point { x: number; y: number }

export const ROOM_WIDTH = 176
export const ROOM_HEIGHT = 80

export function roomNameLines(name: string, capacity: number): string[] {
  const text = name.trim().replace(/\s+/g, ' ')
  if (text.length <= capacity) return [text]
  const space = text.lastIndexOf(' ', capacity)
  const split = space > 0 ? space : capacity
  const rest = text.slice(split).trimStart()
  return [text.slice(0, split), rest.length <= capacity ? rest : `${rest.slice(0, capacity - 1)}…`]
}
