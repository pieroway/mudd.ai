import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'

import CommandPrompt from '../../src/components/CommandPrompt'

it('recalls submitted commands with the arrow keys', () => {
  const onCommand = vi.fn()
  render(<CommandPrompt onCommand={onCommand} />)
  const input = screen.getByTestId('command-input')

  fireEvent.change(input, { target: { value: 'look' } })
  fireEvent.submit(input.closest('form')!)
  fireEvent.change(input, { target: { value: 'north' } })
  fireEvent.submit(input.closest('form')!)

  fireEvent.keyDown(input, { key: 'ArrowUp' })
  expect(input).toHaveValue('north')
  fireEvent.keyDown(input, { key: 'ArrowUp' })
  expect(input).toHaveValue('look')
  fireEvent.keyDown(input, { key: 'ArrowDown' })
  expect(input).toHaveValue('north')
})
