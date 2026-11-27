import { useGSAP } from '@gsap/react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import type { RefObject } from 'react'

gsap.registerPlugin(ScrollTrigger, useGSAP)

export { gsap, ScrollTrigger, useGSAP }

/** Query used with gsap.matchMedia so every animation is skipped for reduced-motion users. */
export const MOTION_OK = '(prefers-reduced-motion: no-preference)'

const canHover = () => window.matchMedia?.('(hover: hover) and (pointer: fine)').matches ?? false
const reduced = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false

/**
 * 3D tilt for liquid-glass cards: the card leans toward the pointer and its specular sheen
 * (CSS vars --mx/--my read by .glass) slides across the surface. Mouse/trackpad only.
 */
export function useTilt<T extends HTMLElement>(
  ref: RefObject<T | null>,
  { max = 7, baseX = 0, baseY = 0 }: { max?: number; baseX?: number; baseY?: number } = {},
) {
  useGSAP(
    () => {
      const el = ref.current
      if (!el || reduced() || !canHover()) return
      gsap.set(el, { transformPerspective: 1000, rotationX: baseX, rotationY: baseY })
      const rx = gsap.quickTo(el, 'rotationX', { duration: 0.7, ease: 'power3.out' })
      const ry = gsap.quickTo(el, 'rotationY', { duration: 0.7, ease: 'power3.out' })
      const move = (e: PointerEvent) => {
        const r = el.getBoundingClientRect()
        const px = (e.clientX - r.left) / r.width
        const py = (e.clientY - r.top) / r.height
        ry(baseY + (px - 0.5) * max * 2)
        rx(baseX - (py - 0.5) * max * 2)
        el.style.setProperty('--mx', `${(px * 100).toFixed(1)}%`)
        el.style.setProperty('--my', `${(py * 100).toFixed(1)}%`)
      }
      const leave = () => {
        rx(baseX)
        ry(baseY)
        el.style.removeProperty('--mx')
        el.style.removeProperty('--my')
      }
      el.addEventListener('pointermove', move)
      el.addEventListener('pointerleave', leave)
      return () => {
        el.removeEventListener('pointermove', move)
        el.removeEventListener('pointerleave', leave)
      }
    },
    { scope: ref },
  )
}

/** Magnetic button: drifts a little toward the pointer, springs back on leave. */
export function useMagnetic<T extends HTMLElement>(ref: RefObject<T | null>, strength = 0.28) {
  useGSAP(
    () => {
      const el = ref.current
      if (!el || reduced() || !canHover()) return
      const x = gsap.quickTo(el, 'x', { duration: 0.5, ease: 'power3.out' })
      const y = gsap.quickTo(el, 'y', { duration: 0.5, ease: 'power3.out' })
      const move = (e: PointerEvent) => {
        const r = el.getBoundingClientRect()
        x((e.clientX - (r.left + r.width / 2)) * strength)
        y((e.clientY - (r.top + r.height / 2)) * strength)
      }
      const leave = () => {
        gsap.to(el, { x: 0, y: 0, duration: 0.8, ease: 'elastic.out(1, 0.4)' })
      }
      el.addEventListener('pointermove', move)
      el.addEventListener('pointerleave', leave)
      return () => {
        el.removeEventListener('pointermove', move)
        el.removeEventListener('pointerleave', leave)
      }
    },
    { scope: ref },
  )
}

/** One-shot entrance for a freshly mounted element (chat turns, cards). */
export function useEntrance<T extends HTMLElement>(ref: RefObject<T | null>, from: gsap.TweenVars = {}) {
  useGSAP(
    () => {
      const mm = gsap.matchMedia()
      mm.add(MOTION_OK, () => {
        gsap.from(ref.current, {
          y: 14,
          autoAlpha: 0,
          filter: 'blur(6px)',
          duration: 0.55,
          ease: 'power3.out',
          clearProps: 'filter',
          ...from,
        })
      })
      return () => mm.revert()
    },
    { scope: ref },
  )
}
