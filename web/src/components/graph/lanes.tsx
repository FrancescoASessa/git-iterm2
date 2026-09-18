import type { GraphCommit } from '../../api/types'

export const LANE_WIDTH = 12
export const ROW_HEIGHT = 22

export function laneX(lane: number): number {
  return 8 + lane * LANE_WIDTH
}

function laneColor(lane: number): string {
  return `var(--ansi-${1 + (lane % 6)})`
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
