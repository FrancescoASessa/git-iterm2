export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div class="empty">
      <p>{title}</p>
      {hint !== undefined && <p class="muted">{hint}</p>}
    </div>
  )
}
