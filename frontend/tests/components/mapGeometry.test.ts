import { describe, expect, it } from 'vitest'
import { roomNameLines } from '../../src/components/mapGeometry'

describe('Map readability', () => {
  it('uses two lines to distinguish rooms with the same name prefix', () => {
    expect(roomNameLines('Wet Bins Chamber East', 15)).toEqual(['Wet Bins', 'Chamber East'])
    expect(roomNameLines('Wet Bins Chamber West', 15)).toEqual(['Wet Bins', 'Chamber West'])
    expect(roomNameLines('Inn', 20)).toEqual(['Inn'])
    expect(roomNameLines('Old Passage', 10)).toEqual(['Old', 'Passage'])
    expect(roomNameLines('A very long room name that cannot fit in two lines', 15)[1]).toMatch(/…$/)
  })

})
