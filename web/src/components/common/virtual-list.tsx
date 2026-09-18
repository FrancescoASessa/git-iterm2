import { useLayoutEffect, useRef, useState } from 'preact/hooks'
import type { ComponentChildren } from 'preact'

export type VirtualWindow = { start: number; end: number; paddingTop: number; totalHeight: number }

export function useVirtualRows({
  total,
  rowHeight,
  viewportHeight,
  scrollTop,
  overscan = 4,
}: {
  total: number
  rowHeight: number
  viewportHeight: number
  scrollTop: number
  overscan?: number
}): VirtualWindow {
  const visible = Math.ceil(viewportHeight / rowHeight)
  const first = Math.floor(scrollTop / rowHeight)
  const start = Math.max(0, first - overscan)
  const end = Math.min(total, first + visible + overscan)
  return { start, end, paddingTop: start * rowHeight, totalHeight: total * rowHeight }
}

export function VirtualList({
  total,
  rowHeight,
  renderRow,
  onReachEnd,
}: {
  total: number
  rowHeight: number
  renderRow: (index: number) => ComponentChildren
  onReachEnd?: () => void
}) {
  const container = useRef<HTMLDivElement | null>(null)
  const [scrollTop, setScrollTop] = useState(0)
  // 400 is only a pre-measure fallback for the very first render, before the
  // layout effect below can read the container's real height.
  const [viewportHeight, setViewportHeight] = useState(400)

  useLayoutEffect(() => {
    const node = container.current
    if (node === null) return
    setViewportHeight(node.clientHeight)
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (entry !== undefined) setViewportHeight(entry.contentRect.height)
    })
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  const visible = useVirtualRows({ total, rowHeight, viewportHeight, scrollTop })

  if (visible.end >= total) onReachEnd?.()

  const rows = []
  for (let index = visible.start; index < visible.end; index += 1) rows.push(renderRow(index))

  return (
    <div
      class="virtual"
      ref={container}
      onScroll={(event) => setScrollTop((event.target as HTMLDivElement).scrollTop)}
    >
      <div style={{ height: `${visible.totalHeight}px`, paddingTop: `${visible.paddingTop}px` }}>
        {rows}
      </div>
    </div>
  )
}
