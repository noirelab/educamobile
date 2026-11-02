export function parseRouteName(raw: string): { nome: string; error: string | null } {
  const nome = raw.trim()
  return nome === '' ? { nome, error: 'Informe o nome' } : { nome, error: null }
}
