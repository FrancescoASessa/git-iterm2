import type { GraphCommit } from '../../api/types'

export const LANE_WIDTH = 12
/** Must equal the stylesheet's `--row-height`: the virtual list places rows by
 * multiplying this, so a row that renders taller drifts the whole list.
 * `tests/components/appearance.test.tsx` asserts the two agree. */
export const ROW_HEIGHT = 26

export function laneX(lane: number): number {
  return 8 + lane * LANE_WIDTH
}

/** Lanes are decoration, not meaning: they come from the panel's own six-colour
 * token set (which has a contrast guarantee on our surfaces in both
 * appearances) rather than from the profile's ANSI palette, which had none. */
function laneColor(lane: number): string {
  return `var(--lane-${lane % 6})`
}

function edgePath(from: number, to: number, half: 'top' | 'bottom'): string {
  const x1 = laneX(from)
  const x2 = laneX(to)
  if (half === 'top') {
    return `M ${x1} 0 C ${x1} ${ROW_HEIGHT * 0.25}, ${x2} ${ROW_HEIGHT * 0.25}, ${x2} ${ROW_HEIGHT / 2}`
  }
  return `M ${x1} ${ROW_HEIGHT / 2} C ${x1} ${ROW_HEIGHT * 0.75}, ${x2} ${ROW_HEIGHT * 0.75}, ${x2} ${ROW_HEIGHT}`
}

export function Lanes({ commit, maxLane }: { commit: GraphCommit; maxLane: number }) {
  const width = laneX(maxLane) + 8
  return (
    <svg class="lanes" width={width} height={ROW_HEIGHT} aria-hidden="true">
      {commit.edges.map((edge, index) => (
        <path
          key={index}
          d={edgePath(edge.from_lane, edge.to_lane, edge.half)}
          data-half={edge.half}
          data-from={edge.from_lane}
          data-to={edge.to_lane}
          fill="none"
          stroke={laneColor(edge.half === 'top' ? edge.from_lane : edge.to_lane)}
          stroke-width="1.5"
        />
      ))}
      <circle cx={laneX(commit.lane)} cy={ROW_HEIGHT / 2} r="3.5" fill={laneColor(commit.lane)} />
    </svg>
  )
}
