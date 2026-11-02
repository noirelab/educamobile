import { describe, expect, it } from 'vitest'
import { breadcrumbFor, visibleNav } from './nav'

describe('visibleNav', () => {
  it('lists the menu items a coordenador can access', () => {
    expect(visibleNav('coordenador').map((item) => item.path)).toEqual([
      '/',
      '/poles',
      '/schools',
      '/classes',
      '/students',
      '/stops',
      '/routes',
    ])
  })

  it('excludes users for diretor', () => {
    expect(visibleNav('diretor').map((item) => item.path)).not.toContain('/users')
  })
})

describe('breadcrumbFor', () => {
  it('labels the section of a path', () => {
    expect(breadcrumbFor('/')).toEqual(['Painel'])
    expect(breadcrumbFor('/classes')).toEqual(['Turmas'])
  })

  it('labels nested pages with the action or detail', () => {
    expect(breadcrumbFor('/poles/new')).toEqual(['Polos', 'Novo'])
    expect(breadcrumbFor('/schools/1/edit')).toEqual(['Escolas', 'Detalhe', 'Editar'])
  })

  it('labels the profile page', () => {
    expect(breadcrumbFor('/profile')).toEqual(['Perfil'])
  })

  it('returns no crumbs for unknown paths', () => {
    expect(breadcrumbFor('/rota-inexistente')).toEqual([])
  })
})
