export function readTokenFromLocation(): string {
  const params = new URLSearchParams(window.location.search)
  const token = params.get('t')
  if (token === null) return ''
  params.delete('t')
  const query = params.toString()
  const url = `${window.location.pathname}${query ? `?${query}` : ''}`
  window.history.replaceState(null, '', url)
  return token
}
