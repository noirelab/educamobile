import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import { server } from '@/test/server'
import { getRefreshToken, getToken, saveSession, setToken } from '@/shared/auth/session'
import { api, onUnauthorized } from '@/shared/api/client'

describe('api client', () => {
  it('sends bearer token and calls onUnauthorized on 401', async () => {
    setToken('abc')
    const spy = vi.fn()
    onUnauthorized(spy)
    server.use(http.get('*/escolas', ({ request }) =>
      request.headers.get('Authorization') === 'Bearer abc' ? new HttpResponse(null, { status: 401 }) : HttpResponse.json([])))
    await expect(api('/escolas')).rejects.toMatchObject({ status: 401 })
    expect(spy).toHaveBeenCalledOnce()
  })

  it('returns undefined on 204', async () => {
    server.use(http.delete('*/escolas/1', () => new HttpResponse(null, { status: 204 })))
    await expect(api('/escolas/1', { method: 'DELETE' })).resolves.toBeUndefined()
  })

  it('does not call onUnauthorized for login 401', async () => {
    const spy = vi.fn()
    onUnauthorized(spy)
    server.use(http.post('*/auth/login', () => HttpResponse.json({ detail: 'E-mail ou senha incorretos' }, { status: 401 })))
    await expect(api('/auth/login', { method: 'POST', form: new URLSearchParams({ username: 'a', password: 'b' }) }))
      .rejects.toMatchObject({ status: 401, detail: 'E-mail ou senha incorretos' })
    expect(spy).not.toHaveBeenCalled()
  })

  it('omits undefined query params', async () => {
    let seen = ''
    server.use(http.get('*/escolas', ({ request }) => {
      seen = new URL(request.url).search
      return HttpResponse.json([])
    }))
    await api('/escolas', { query: { limit: 200, offset: 0, nome: undefined, ativo: true } })
    expect(seen).toBe('?limit=200&offset=0&ativo=true')
  })

  it('sends json body with content type', async () => {
    let body: unknown = null
    let type = ''
    server.use(http.post('*/escolas', async ({ request }) => {
      type = request.headers.get('Content-Type') ?? ''
      body = await request.json()
      return HttpResponse.json({ id: 1 }, { status: 201 })
    }))
    await expect(api('/escolas', { method: 'POST', json: { nome: 'X' } })).resolves.toEqual({ id: 1 })
    expect(type).toContain('application/json')
    expect(body).toEqual({ nome: 'X' })
  })

  it('sends form as urlencoded', async () => {
    let type = ''
    let text = ''
    server.use(http.post('*/auth/login', async ({ request }) => {
      type = request.headers.get('Content-Type') ?? ''
      text = await request.text()
      return HttpResponse.json({ access_token: 't' })
    }))
    await api('/auth/login', { method: 'POST', form: new URLSearchParams({ username: 'a@b.c', password: 'x y' }) })
    expect(type).toContain('application/x-www-form-urlencoded')
    expect(text).toBe('username=a%40b.c&password=x+y')
  })

  it('throws ApiError with status 0 on network failure', async () => {
    server.use(http.get('*/escolas', () => HttpResponse.error()))
    await expect(api('/escolas')).rejects.toMatchObject({ status: 0 })
  })

  it('defaults base url to http://localhost:8000 when env is empty', async () => {
    vi.stubEnv('VITE_API_URL', '')
    try {
      server.use(http.get('http://localhost:8000/escolas', () => HttpResponse.json([{ id: 9 }])))
      await expect(api('/escolas')).resolves.toEqual([{ id: 9 }])
    } finally {
      vi.unstubAllEnvs()
    }
  })

  describe('session renewal', () => {
    const NOVO = { access_token: 'novo', refresh_token: 'refresh-2', expires_in: 900, token_type: 'bearer' }

    function login(expiresIn = 900) {
      saveSession({ access_token: 'velho', refresh_token: 'refresh-1', expires_in: expiresIn })
    }

    it('renews on 401 and repeats the request exactly once', async () => {
      login()
      const seen: string[] = []
      server.use(
        http.post('*/auth/refresh', async ({ request }) => {
          expect(await request.json()).toEqual({ refresh_token: 'refresh-1' })
          return HttpResponse.json(NOVO)
        }),
        http.get('*/escolas', ({ request }) => {
          const auth = request.headers.get('Authorization') ?? ''
          seen.push(auth)
          return auth === 'Bearer novo' ? HttpResponse.json([{ id: 1 }]) : new HttpResponse(null, { status: 401 })
        }),
      )

      await expect(api('/escolas')).resolves.toEqual([{ id: 1 }])

      expect(seen).toEqual(['Bearer velho', 'Bearer novo'])
      expect(getToken()).toBe('novo')
      expect(getRefreshToken()).toBe('refresh-2')
    })

    it('gives up after one retry when the new token is also refused', async () => {
      login()
      const spy = vi.fn()
      onUnauthorized(spy)
      let calls = 0
      server.use(
        http.post('*/auth/refresh', () => HttpResponse.json(NOVO)),
        http.get('*/escolas', () => {
          calls += 1
          return new HttpResponse(null, { status: 401 })
        }),
      )

      await expect(api('/escolas')).rejects.toMatchObject({ status: 401 })

      expect(calls).toBe(2)
      expect(spy).toHaveBeenCalledOnce()
    })

    it('clears the session and signs out when the refresh token is refused', async () => {
      login()
      const spy = vi.fn()
      onUnauthorized(spy)
      server.use(
        http.post('*/auth/refresh', () => HttpResponse.json({ detail: 'Sessão inválida' }, { status: 401 })),
        http.get('*/escolas', () => new HttpResponse(null, { status: 401 })),
      )

      await expect(api('/escolas')).rejects.toMatchObject({ status: 401 })

      expect(spy).toHaveBeenCalledOnce()
      expect(getToken()).toBeNull()
      expect(getRefreshToken()).toBeNull()
    })

    it('shares one renewal between simultaneous requests', async () => {
      login()
      let refreshCalls = 0
      server.use(
        http.post('*/auth/refresh', async () => {
          refreshCalls += 1
          await new Promise((resolve) => setTimeout(resolve, 20))
          return HttpResponse.json(NOVO)
        }),
        http.get('*/escolas', ({ request }) =>
          request.headers.get('Authorization') === 'Bearer novo'
            ? HttpResponse.json([])
            : new HttpResponse(null, { status: 401 }),
        ),
        http.get('*/paradas', ({ request }) =>
          request.headers.get('Authorization') === 'Bearer novo'
            ? HttpResponse.json([])
            : new HttpResponse(null, { status: 401 }),
        ),
      )

      await Promise.all([api('/escolas'), api('/paradas'), api('/escolas')])

      expect(refreshCalls).toBe(1)
    })

    it('renews before the access token expires, without waiting for a 401', async () => {
      login(10)
      const seen: string[] = []
      server.use(
        http.post('*/auth/refresh', () => HttpResponse.json(NOVO)),
        http.get('*/escolas', ({ request }) => {
          seen.push(request.headers.get('Authorization') ?? '')
          return HttpResponse.json([])
        }),
      )

      await api('/escolas')

      expect(seen).toEqual(['Bearer novo'])
    })

    it('does not renew when there is no refresh token', async () => {
      setToken('so-acesso')
      const spy = vi.fn()
      onUnauthorized(spy)
      let refreshCalls = 0
      server.use(
        http.post('*/auth/refresh', () => {
          refreshCalls += 1
          return HttpResponse.json(NOVO)
        }),
        http.get('*/escolas', () => new HttpResponse(null, { status: 401 })),
      )

      await expect(api('/escolas')).rejects.toMatchObject({ status: 401 })

      expect(refreshCalls).toBe(0)
      expect(spy).toHaveBeenCalledOnce()
    })
  })
})
