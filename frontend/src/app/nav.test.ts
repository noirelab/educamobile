import { describe, expect, it } from 'vitest'
import { breadcrumbFor, visibleNav } from './nav'

describe('visibleNav', () => {
  it('lists the menu items a gestor can access', () => {
    expect(visibleNav('gestor').map((item) => item.path)).toEqual([
      '/',
      '/schools',
      '/students',
      '/stops',
      '/routes',
      '/users',
    ])
  })

  it.each(['motorista', 'monitor', 'responsavel'] as const)('shows no registration menu for %s', (role) => {
    expect(visibleNav(role)).toEqual([])
  })
})

describe('breadcrumbFor', () => {
  it('labels the section of a path', () => {
    expect(breadcrumbFor('/')).toEqual(['Painel'])
    expect(breadcrumbFor('/students')).toEqual(['Estudantes'])
  })

  it('labels nested pages with the action or detail', () => {
    expect(breadcrumbFor('/students/new')).toEqual(['Estudantes', 'Novo'])
    expect(breadcrumbFor('/schools/1/edit')).toEqual(['Escolas', 'Detalhe', 'Editar'])
  })

  it('labels the profile page', () => {
    expect(breadcrumbFor('/profile')).toEqual(['Perfil'])
  })

  it('returns no crumbs for unknown paths', () => {
    expect(breadcrumbFor('/rota-inexistente')).toEqual([])
  })
})
