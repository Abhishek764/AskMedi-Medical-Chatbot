import { lazy, Suspense, useRef, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { gsap, MOTION_OK, useGSAP } from '../lib/motion'

// WebGL background: loaded on its own so the chat screen never pays for it.
const Silk = lazy(() => import('./reactbits/Silk'))

export const DISCLAIMER =
  'AskMedi gives general health information from cited sources. It is not medical advice, a diagnosis or a prescription. In an emergency, call your local emergency number.'

/** The [+] mark: a medical cross held in citation brackets — every answer has a source. */
export function Mark({ className = 'size-7' }: { className?: string }) {
  return (
    <svg viewBox="0 0 256 256" aria-hidden className={className}>
      <path
        fill="currentColor"
        d="M76 44H28V212H76V188H52V68H76ZM180 44H228V212H180V188H204V68H180ZM110 84H146V110H172V146H146V172H110V146H84V110H110Z"
      />
    </svg>
  )
}

export function Logo({ to = '/' }: { to?: string }) {
  return (
    <Link to={to} className="group flex items-center gap-2.5 rounded-lg" aria-label="AskMedi home">
      <span className="glass grid size-9 place-items-center rounded-xl text-accent transition-transform group-hover:-rotate-3">
        <Mark className="size-5" />
      </span>
      <span className="font-display text-[1.05rem] font-semibold tracking-tight text-fg">
        Ask<span className="text-accent">Medi</span>
      </span>
    </Link>
  )
}

/** Slow matte-green silk behind marketing and auth screens, sunk into black at the edges. */
export function Backdrop({ strength = 0.75 }: { strength?: number }) {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <Suspense fallback={null}>
        <div className="absolute inset-0" style={{ opacity: strength }}>
          <Silk color="#0f2a19" sheenColor="#4ade80" speed={3} scale={1.1} sheen={0.45} glow={0.25} noiseIntensity={1.2} rotation={-0.25} />
        </div>
      </Suspense>
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_50%_20%,transparent_10%,var(--color-ink)_80%)]" />
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-ink/20 to-ink" />
    </div>
  )
}

/**
 * SVG lens used by .glass-liquid (Chromium): low-frequency noise displaces whatever sits behind
 * the glass, so edges bend like light through a thick pane of liquid glass.
 */
export function LiquidFilter() {
  return (
    <svg aria-hidden width="0" height="0" className="absolute">
      <filter id="liquid-refract" x="0" y="0" width="100%" height="100%" colorInterpolationFilters="sRGB">
        <feTurbulence type="fractalNoise" baseFrequency="0.006 0.01" numOctaves="2" seed="11" result="noise" />
        <feGaussianBlur in="noise" stdDeviation="3" result="soft" />
        <feDisplacementMap in="SourceGraphic" in2="soft" scale="42" xChannelSelector="R" yChannelSelector="G" />
      </filter>
    </svg>
  )
}

/** Animated ambient light behind app screens (chat, settings): cheap CSS, no WebGL. */
export function Ambient() {
  return (
    <div aria-hidden className="ambient">
      <div className="grid" />
      <div className="orb orb-a" />
      <div className="orb orb-b" />
      <div className="orb orb-c" />
    </div>
  )
}

/** Thin indeterminate bar pinned to the top: instant feedback for anything slower than ~300 ms. */
export function TopProgress({ active }: { active: boolean }) {
  return (
    <div
      role="progressbar"
      aria-hidden={!active}
      aria-label="Loading"
      className={`pointer-events-none fixed inset-x-0 top-0 z-50 h-0.5 overflow-hidden transition-opacity duration-300 ${
        active ? 'opacity-100' : 'opacity-0'
      }`}
    >
      <div className="h-full w-full origin-left animate-progress bg-gradient-to-r from-transparent via-accent to-lime shadow-[0_0_12px_var(--color-accent)]" />
    </div>
  )
}

export function Skeleton({ className = '' }: { className?: string }) {
  return <div aria-hidden className={`skeleton ${className}`} />
}

/** Full-screen placeholder shown while the session is restored. */
export function AppSkeleton() {
  return (
    <div className="flex h-dvh" aria-busy="true" aria-label="Loading AskMedi">
      <Ambient />
      <TopProgress active />
      <aside className="hidden w-72 flex-col gap-3 border-r border-line p-4 md:flex">
        <Skeleton className="h-9 w-32" />
        <Skeleton className="mt-2 h-11 w-full rounded-xl" />
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-8" />
        ))}
      </aside>
      <main className="flex flex-1 flex-col items-center gap-4 px-4 pt-24">
        <Skeleton className="h-8 w-72 max-w-full" />
        <Skeleton className="h-4 w-96 max-w-full" />
        <div className="mt-6 grid w-full max-w-3xl gap-3 sm:grid-cols-2">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-20 rounded-2xl" />
          ))}
        </div>
      </main>
    </div>
  )
}

/** Centered glass card used by sign-in, sign-up and consent screens. */
export function CardPage({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  const root = useRef<HTMLDivElement>(null)
  useGSAP(
    () => {
      const mm = gsap.matchMedia()
      mm.add(MOTION_OK, () => {
        gsap
          .timeline({ defaults: { ease: 'power3.out' } })
          .from('.cp-logo', { y: -16, autoAlpha: 0, duration: 0.6 })
          .from('.cp-card', { y: 40, rotationX: 14, transformPerspective: 900, autoAlpha: 0, duration: 0.9, ease: 'expo.out' }, '-=0.3')
          .from('.cp-card label, .cp-card button, .cp-card p', { y: 10, autoAlpha: 0, stagger: 0.04, duration: 0.4 }, '-=0.5')
      })
      return () => mm.revert()
    },
    { scope: root },
  )
  return (
    <main className="relative grid min-h-dvh place-items-center px-4 py-10">
      <Backdrop strength={0.6} />
      <div ref={root} className="w-full max-w-md">
        <div className="cp-logo mb-8 flex justify-center">
          <Logo />
        </div>
        <section className="cp-card glass glass-liquid rounded-3xl p-7 sm:p-8">
          <h1 className="font-display text-xl font-semibold tracking-tight">{title}</h1>
          {subtitle ? <p className="mt-1.5 text-sm text-muted">{subtitle}</p> : null}
          <div className="mt-6">{children}</div>
        </section>
        <p className="mt-6 text-center text-xs leading-relaxed text-faint">{DISCLAIMER}</p>
      </div>
    </main>
  )
}

export function Field(props: {
  label: string
  hint?: string
  type?: string
  value: string
  onChange: (v: string) => void
  autoComplete?: string
  minLength?: number
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-fg">{props.label}</span>
      {props.hint ? <span className="ml-1.5 text-xs text-faint">{props.hint}</span> : null}
      <input
        required
        type={props.type ?? 'text'}
        value={props.value}
        autoComplete={props.autoComplete}
        minLength={props.minLength}
        onChange={(e) => props.onChange(e.target.value)}
        className="input mt-1.5"
      />
    </label>
  )
}

export function ErrorText({ error }: { error: string | null }) {
  return error ? (
    <p role="alert" className="rounded-xl border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-rose-200">
      {error}
    </p>
  ) : null
}

export const primaryButton = 'btn btn-primary w-full'

/** Slim top bar for secondary pages (settings, policies, dashboard). */
export function PageHeader({ children }: { children?: ReactNode }) {
  return (
    <>
    <Ambient />
    <header className="glass glass-strong sticky top-0 z-30 flex items-center justify-between rounded-none border-x-0 border-t-0 px-4 py-3 sm:px-6">
      <Logo to="/chat" />
      <nav className="flex items-center gap-2 text-sm">
        {children}
        <Link to="/chat" className="btn btn-ghost min-h-9 px-3 text-sm">
          Back to chat
        </Link>
      </nav>
    </header>
    </>
  )
}
