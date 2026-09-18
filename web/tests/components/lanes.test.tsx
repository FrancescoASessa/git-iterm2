import { render } from '@testing-library/preact'
import { describe, expect, it } from 'vitest'

import { Lanes, ROW_HEIGHT, laneX } from '../../src/components/graph/lanes'
import type { GraphCommit } from '../../src/api/types'

const commit: GraphCommit = {
  sha: 'a'.repeat(40),
  parents: ['b'.repeat(40)],
  author: 'Ann',
  timestamp: 1,
  subject: 'work',
  refs: [],
  lane: 1,
  edges: [
    { from_lane: 0, to_lane: 0, half: 'top' },
    { from_lane: 1, to_lane: 1, half: 'top' },
    { from_lane: 1, to_lane: 0, half: 'bottom' },
  ],
}

describe('Lanes', () => {
  it('draws one path per edge and a dot on the commit lane', () => {
    const { container } = render(<Lanes commit={commit} maxLane={1} />)
    const svg = container.querySelector('svg')

    expect(svg).toHaveAttribute('aria-hidden', 'true')
    expect(svg).toHaveAttribute('height', String(ROW_HEIGHT))
    expect(svg?.getAttribute('width')).toBe(String(laneX(1) + 8))
    expect(container.querySelectorAll('path')).toHaveLength(3)

    const dot = container.querySelector('circle')
    expect(dot?.getAttribute('cx')).toBe(String(laneX(1)))
    expect(dot?.getAttribute('cy')).toBe(String(ROW_HEIGHT / 2))
  })

  it('routes top edges from the row top to the center and bottom edges to the row bottom', () => {
    const { container } = render(<Lanes commit={commit} maxLane={1} />)
    const top = container.querySelector('path[data-half="top"][data-from="0"]')
    const bottom = container.querySelector('path[data-half="bottom"][data-from="1"]')

    expect(top?.getAttribute('d')).toBe(
      `M ${laneX(0)} 0 C ${laneX(0)} ${ROW_HEIGHT * 0.25}, ${laneX(0)} ${ROW_HEIGHT * 0.25}, ${laneX(0)} ${ROW_HEIGHT / 2}`,
    )
    expect(bottom?.getAttribute('d')).toBe(
      `M ${laneX(1)} ${ROW_HEIGHT / 2} C ${laneX(1)} ${ROW_HEIGHT * 0.75}, ${laneX(0)} ${ROW_HEIGHT * 0.75}, ${laneX(0)} ${ROW_HEIGHT}`,
    )
  })
})
