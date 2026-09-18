import { render, screen } from '@testing-library/preact'
import { afterEach, describe, expect, it } from 'vitest'

import { VirtualList, useVirtualRows } from '../../src/components/common/virtual-list'

describe('useVirtualRows', () => {
  it('computes the visible window with overscan', () => {
    const window1 = useVirtualRows({
      total: 1000,
      rowHeight: 20,
      viewportHeight: 100,
      scrollTop: 0,
      overscan: 2,
    })
    expect(window1).toEqual({ start: 0, end: 7, paddingTop: 0, totalHeight: 20000 })

    const window2 = useVirtualRows({
      total: 1000,
      rowHeight: 20,
      viewportHeight: 100,
      scrollTop: 400,
      overscan: 2,
    })
    expect(window2.start).toBe(18)
    expect(window2.end).toBe(27)
    expect(window2.paddingTop).toBe(360)
  })

  it('never exceeds the total', () => {
    const window = useVirtualRows({
      total: 3,
      rowHeight: 20,
      viewportHeight: 500,
      scrollTop: 0,
      overscan: 5,
    })
    expect(window).toEqual({ start: 0, end: 3, paddingTop: 0, totalHeight: 60 })
  })
})

describe('VirtualList', () => {
  let originalClientHeight: PropertyDescriptor | undefined

  afterEach(() => {
    if (originalClientHeight) {
      Object.defineProperty(HTMLElement.prototype, 'clientHeight', originalClientHeight)
    } else {
      delete (HTMLElement.prototype as { clientHeight?: number }).clientHeight
    }
    originalClientHeight = undefined
  })

  it('measures the container after mount instead of using the 400px default', () => {
    originalClientHeight = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'clientHeight')
    Object.defineProperty(HTMLElement.prototype, 'clientHeight', {
      configurable: true,
      value: 1000,
    })

    render(
      <VirtualList
        total={200}
        rowHeight={20}
        renderRow={(index) => <div key={index}>row {index}</div>}
      />,
    )

    // 1000px viewport / 20px rows = 50 visible + default overscan 4 = 54 rendered rows.
    // The stale 400px default would only render 24.
    expect(screen.getAllByText(/^row \d+$/)).toHaveLength(54)
  })
})
