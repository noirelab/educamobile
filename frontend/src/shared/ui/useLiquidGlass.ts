import { useEffect, useId, useRef, useSyncExternalStore, type RefObject } from 'react'
import { buildDisplacementMap, buildSpecularMap } from './liquidMap'

export const MAX_WIDTH = 1600
export const MAX_HEIGHT = 1200
export const BASE_SCALE = 36
const DEBOUNCE_MS = 120

export function chooseBezel(width: number, height: number) {
  return Math.max(2, Math.min(24, 0.25 * Math.min(width, height)))
}

export function shouldBuildMap(width: number, height: number) {
  return width >= 16 && height >= 16 && width <= MAX_WIDTH && height <= MAX_HEIGHT
}

export function chooseRadius(width: number, height: number, desired: number) {
  return Math.max(1, Math.min(desired, Math.floor(Math.min(width, height) / 2)))
}

export function detectLiquidSupport() {
  if (typeof navigator === 'undefined' || typeof CSS === 'undefined' || typeof CSS.supports !== 'function') return false
  const ua = navigator.userAgent
  const chromium = /Chrome|Chromium|Edg\//.test(ua) && !/Firefox/.test(ua)
  return chromium && CSS.supports('backdrop-filter', 'url(#a)')
}

let supportCache: boolean | null = null
export function liquidSupported() {
  if (supportCache === null) supportCache = detectLiquidSupport()
  return supportCache
}

export type LiquidEntry = { id: string; width: number; height: number; displacement: string; specular: string }

const entries = new Map<string, LiquidEntry>()
const listeners = new Set<() => void>()
let snapshot: LiquidEntry[] = []

function emit() {
  snapshot = Array.from(entries.values())
  listeners.forEach((listener) => listener())
}

export function subscribeLiquid(listener: () => void) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

export function getLiquidEntries() {
  return snapshot
}

export function useLiquidEntries() {
  return useSyncExternalStore(subscribeLiquid, getLiquidEntries, getLiquidEntries)
}

function toDataUrl(data: Uint8ClampedArray, width: number, height: number) {
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const context = canvas.getContext('2d')
  if (!context) return ''
  const imageData = context.createImageData(width, height)
  imageData.data.set(data)
  context.putImageData(imageData, 0, 0)
  return canvas.toDataURL()
}

const reducedMotion = () =>
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

export function useLiquidGlass<T extends HTMLElement>(enabled: boolean, radius = 22, interactive = false): RefObject<T> {
  const ref = useRef<T>(null)
  const rawId = useId()
  const id = `lg-${rawId.replace(/[^a-zA-Z0-9]/g, '')}`

  useEffect(() => {
    const element = ref.current
    if (!element) return
    const supported = enabled && liquidSupported()
    element.classList.toggle('glass-fallback', enabled && !supported)
    if (!supported || typeof ResizeObserver === 'undefined') return

    let timer: ReturnType<typeof setTimeout> | undefined
    let animation: number | undefined
    let scale = BASE_SCALE

    const clear = () => {
      element.style.removeProperty('backdrop-filter')
      element.style.removeProperty('-webkit-backdrop-filter')
      element.classList.add('glass-fallback')
      if (entries.delete(id)) emit()
    }

    const build = () => {
      const width = Math.round(element.offsetWidth)
      const height = Math.round(element.offsetHeight)
      if (!shouldBuildMap(width, height)) {
        clear()
        return
      }
      const r = chooseRadius(width, height, radius)
      const bezel = chooseBezel(width, height)
      entries.set(id, {
        id,
        width,
        height,
        displacement: toDataUrl(buildDisplacementMap(width, height, r, bezel), width, height),
        specular: toDataUrl(buildSpecularMap(width, height, r, bezel), width, height),
      })
      emit()
      const value = `url(#${id}) blur(2px) saturate(180%) brightness(1.05)`
      element.style.setProperty('backdrop-filter', value)
      element.style.setProperty('-webkit-backdrop-filter', value)
      element.classList.remove('glass-fallback')
    }

    const displacementNode = () => document.getElementById(`${id}-d`)

    const animateTo = (target: number) => {
      if (animation) cancelAnimationFrame(animation)
      const from = scale
      const start = performance.now()
      const step = (now: number) => {
        const t = Math.min((now - start) / 250, 1)
        scale = from + (target - from) * t
        displacementNode()?.setAttribute('scale', String(scale))
        if (t < 1) animation = requestAnimationFrame(step)
      }
      animation = requestAnimationFrame(step)
    }

    const enter = () => {
      if (!reducedMotion()) animateTo(BASE_SCALE * 1.25)
    }
    const leave = () => {
      if (!reducedMotion()) animateTo(BASE_SCALE)
    }

    const observer = new ResizeObserver(() => {
      if (timer) clearTimeout(timer)
      timer = setTimeout(build, DEBOUNCE_MS)
    })
    observer.observe(element)
    build()
    if (interactive) {
      element.addEventListener('pointerenter', enter)
      element.addEventListener('pointerleave', leave)
    }

    return () => {
      observer.disconnect()
      if (timer) clearTimeout(timer)
      if (animation) cancelAnimationFrame(animation)
      element.removeEventListener('pointerenter', enter)
      element.removeEventListener('pointerleave', leave)
      element.style.removeProperty('backdrop-filter')
      element.style.removeProperty('-webkit-backdrop-filter')
      if (entries.delete(id)) emit()
    }
  }, [enabled, radius, interactive, id])

  return ref
}
