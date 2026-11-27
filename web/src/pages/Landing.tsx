import { ArrowRight, BookOpenCheck, CircleSlash, Quote, Siren, type LucideIcon } from 'lucide-react'
import { useRef, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Backdrop, DISCLAIMER, Logo, Mark } from '../components/Layout'
import { gsap, MOTION_OK, useGSAP, useMagnetic, useTilt } from '../lib/motion'

const POINTS: { icon: LucideIcon; title: string; body: string }[] = [
  {
    icon: BookOpenCheck,
    title: 'Trusted sources only',
    body: 'MedlinePlus health topics, FDA drug labels and peer-reviewed research reviews. Nothing scraped from forums.',
  },
  {
    icon: Quote,
    title: 'Every sentence is cited',
    body: 'Tap a number to see exactly which document and section a claim came from.',
  },
  {
    icon: CircleSlash,
    title: 'Says "I don\'t know"',
    body: 'When the sources don\'t cover your question, AskMedi tells you instead of guessing.',
  },
  {
    icon: Siren,
    title: 'Safety comes first',
    body: 'Emergency and crisis messages get helpline numbers straight away, not a chat reply.',
  },
]

// The real pipeline, in order: numbering here carries meaning.
const STEPS = [
  ['You ask', 'A question about a condition, a symptom or a medicine, in your own words.'],
  ['It searches 1,677 documents', 'Keyword and meaning search across the medical library, then the best passages are ranked.'],
  ['Every sentence is checked', 'Claims the sources don\'t support are dropped. What is left comes back with its citations.'],
]

const SOURCES = [
  ['1,000+', 'MedlinePlus topics'],
  ['300+', 'FDA drug labels'],
  ['359', 'research reviews'],
]

const HEADLINE = ['Health', 'answers', 'with', 'the']

function Cite({ n }: { n: number }) {
  return (
    <sup className="ml-0.5 rounded-md bg-accent/15 px-1 py-px font-mono text-[10px] font-medium text-accent">{n}</sup>
  )
}

function Magnetic({ to, className, children }: { to: string; className: string; children: ReactNode }) {
  const ref = useRef<HTMLAnchorElement>(null)
  useMagnetic(ref)
  return (
    <Link ref={ref} to={to} className={className}>
      {children}
    </Link>
  )
}

/** A static example of a real answer: the hero shows the product instead of describing it. */
function DemoAnswer() {
  const card = useRef<HTMLElement>(null)
  useTilt(card, { max: 9, baseY: -8, baseX: 3 })
  return (
    <figure
      ref={card}
      className="glass glass-liquid relative w-full max-w-md rounded-[1.75rem] p-5 will-change-transform [transform-style:preserve-3d] sm:p-6"
    >
      <p className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-md bg-accent px-4 py-2 text-sm font-medium text-accent-ink [transform:translateZ(30px)]">
        What are the symptoms of dengue?
      </p>
      <blockquote className="mt-4 space-y-2 text-[0.9375rem] leading-relaxed text-fg/90 [transform:translateZ(18px)]">
        <p>
          Dengue usually starts with a sudden high fever, severe headache and pain behind the eyes
          <Cite n={1} />. Muscle and joint pain, nausea and a rash are also common
          <Cite n={1} />
          <Cite n={2} />.
        </p>
      </blockquote>
      <figcaption className="mt-4 space-y-1.5 border-t border-line pt-3 font-mono text-[11px] text-muted">
        <p>
          <span className="text-accent">[1]</span> Dengue Fever · MedlinePlus
        </p>
        <p>
          <span className="text-accent">[2]</span> Dengue: clinical review · PMC
        </p>
      </figcaption>
      <span className="absolute -right-3 -top-3 rounded-full border border-accent/30 bg-ink-2 px-2.5 py-1 font-mono text-[10px] uppercase tracking-wider text-accent shadow-lg [transform:translateZ(50px)]">
        2 sources
      </span>
    </figure>
  )
}

function Feature({ icon: Icon, title, body }: (typeof POINTS)[number]) {
  const ref = useRef<HTMLDivElement>(null)
  useTilt(ref, { max: 6 })
  return (
    <div ref={ref} className="feature glass h-full rounded-2xl p-6 will-change-transform">
      <span className="grid size-10 place-items-center rounded-xl border border-accent/20 bg-accent/10 text-accent shadow-[inset_0_1px_0_rgb(255_255_255/0.15)]">
        <Icon className="size-5" aria-hidden />
      </span>
      <h3 className="mt-5 font-semibold text-fg">{title}</h3>
      <p className="mt-1.5 text-sm leading-relaxed text-muted">{body}</p>
    </div>
  )
}

export default function Landing() {
  const root = useRef<HTMLDivElement>(null)

  useGSAP(
    () => {
      const mm = gsap.matchMedia()
      mm.add(MOTION_OK, () => {
        // Hero: words rise out of their line boxes, then copy, actions and the 3D answer card.
        gsap
          .timeline({ defaults: { ease: 'power4.out' } })
          .from('.hero-eyebrow', { y: 12, autoAlpha: 0, duration: 0.6 })
          .from(
            '.hero-word',
            { yPercent: 115, rotationX: -50, transformOrigin: '50% 100%', duration: 1, stagger: 0.07 },
            '-=0.3',
          )
          .from('.hero-bracket', { scaleY: 0, autoAlpha: 0, duration: 0.5, stagger: 0.1, ease: 'back.out(2)' }, '-=0.5')
          .from('.hero-copy', { y: 18, autoAlpha: 0, duration: 0.8 }, '-=0.5')
          .from('.hero-cta', { y: 18, autoAlpha: 0, duration: 0.7, stagger: 0.08 }, '-=0.6')
          .from('.hero-stat', { y: 14, autoAlpha: 0, duration: 0.6, stagger: 0.07 }, '-=0.5')
          .from(
            '.hero-demo',
            {
              autoAlpha: 0,
              y: 60,
              z: -300,
              rotationY: -35,
              rotationX: 10,
              transformPerspective: 1200,
              duration: 1.6,
              ease: 'expo.out',
            },
            0.35,
          )

        // Idle: the answer card floats.
        gsap.to('.hero-float', { y: -12, duration: 3.2, ease: 'sine.inOut', repeat: -1, yoyo: true, delay: 1.8 })

        // Feature cards rise in 3D as they enter the viewport.
        gsap.utils.toArray<HTMLElement>('.feature-row').forEach((row) => {
          gsap.fromTo(
            row.querySelectorAll('.feature'),
            { y: 50, rotationX: -18, transformPerspective: 900, autoAlpha: 0 },
            {
              y: 0,
              rotationX: 0,
              autoAlpha: 1,
              duration: 1,
              stagger: 0.12,
              ease: 'power3.out',
              scrollTrigger: { trigger: row, start: 'top 85%', once: true },
            },
          )
        })

        // How it works: the rail fills with scroll and each step lights up as it is reached.
        gsap.fromTo(
          '.steps-rail-fill',
          { scaleY: 0 },
          {
            scaleY: 1,
            ease: 'none',
            scrollTrigger: { trigger: '.steps', start: 'top 70%', end: 'bottom 60%', scrub: 0.6 },
          },
        )
        gsap.utils.toArray<HTMLElement>('.step').forEach((step) => {
          gsap.from(step, {
            x: -24,
            autoAlpha: 0.15,
            duration: 0.8,
            ease: 'power3.out',
            scrollTrigger: { trigger: step, start: 'top 75%', toggleActions: 'play none none reverse' },
          })
        })

        gsap.from('.not-box', {
          y: 30,
          autoAlpha: 0,
          duration: 0.9,
          ease: 'power3.out',
          scrollTrigger: { trigger: '.not-box', start: 'top 90%', once: true },
        })
      })
      return () => mm.revert()
    },
    { scope: root },
  )

  return (
    <div ref={root} className="relative min-h-dvh overflow-x-clip">
      <Backdrop />
      <header className="mx-auto flex max-w-6xl items-center justify-between px-4 py-5 sm:px-6">
        <Logo />
        <nav className="flex items-center gap-2 text-sm">
          <Link to="/login" className="btn min-h-10 px-3 text-sm text-fg hover:bg-white/5">
            Sign in
          </Link>
          <Magnetic to="/register" className="btn btn-primary min-h-10 px-4 text-sm">
            Get started
          </Magnetic>
        </nav>
      </header>

      <main className="mx-auto max-w-6xl px-4 pb-16 sm:px-6">
        <section className="grid items-center gap-14 pt-10 lg:grid-cols-[1.15fr_1fr] lg:pt-20">
          <div>
            <p className="hero-eyebrow eyebrow">Medical answers, sourced</p>
            <h1 className="mt-4 font-display text-[2.3rem] font-semibold leading-[1.1] tracking-tight [perspective:600px] sm:text-5xl xl:text-[3.5rem]">
              {HEADLINE.map((w) => (
                <span key={w} className="inline-block overflow-hidden pb-1 align-bottom">
                  <span className="hero-word inline-block">{w}&nbsp;</span>
                </span>
              ))}
              <span className="inline-block whitespace-nowrap pb-1 align-bottom">
                <span className="hero-bracket inline-block font-mono font-normal text-accent/60">[</span>
                <span className="inline-block overflow-hidden align-bottom">
                  <span className="hero-word inline-block bg-gradient-to-r from-accent to-lime bg-clip-text text-transparent">
                    sources
                  </span>
                </span>
                <span className="hero-bracket inline-block font-mono font-normal text-accent/60">]</span>
              </span>{' '}
              <span className="inline-block overflow-hidden pb-1 align-bottom">
                <span className="hero-word inline-block">showing.</span>
              </span>
            </h1>
            <p className="hero-copy mt-6 max-w-xl text-lg leading-relaxed text-muted">
              Ask about a condition, a symptom or a medicine. AskMedi answers in plain language from trusted medical
              sources and shows you where every sentence came from.
            </p>
            <div className="mt-9 flex flex-wrap items-center gap-3">
              <span className="hero-cta inline-block">
                <Magnetic to="/register" className="btn btn-primary h-12 px-6 text-base">
                  Ask your first question <ArrowRight className="size-4" aria-hidden />
                </Magnetic>
              </span>
              <Link to="/login" className="hero-cta btn btn-ghost h-12 px-5 text-base">
                I have an account
              </Link>
            </div>
            <dl className="mt-12 flex flex-wrap gap-x-8 gap-y-4">
              {SOURCES.map(([n, label]) => (
                <div key={label} className="hero-stat">
                  <dt className="sr-only">{label}</dt>
                  <dd className="font-display text-2xl font-semibold text-fg">{n}</dd>
                  <dd className="text-xs text-muted">{label}</dd>
                </div>
              ))}
            </dl>
          </div>
          <div className="hero-demo flex justify-center [perspective:1200px] lg:justify-end">
            <div className="hero-float w-full max-w-md">
              <DemoAnswer />
            </div>
          </div>
        </section>

        <section aria-labelledby="why" className="mt-32">
          <p className="eyebrow">Why people trust it</p>
          <h2 id="why" className="mt-3 font-display text-2xl font-semibold tracking-tight sm:text-3xl">
            Built to be checked, not trusted blindly
          </h2>
          <ul className="feature-row mt-10 grid gap-4 [perspective:1200px] sm:grid-cols-2">
            {POINTS.map((p) => (
              <li key={p.title}>
                <Feature {...p} />
              </li>
            ))}
          </ul>
        </section>

        <section aria-labelledby="how" className="mt-32 grid gap-12 lg:grid-cols-[0.9fr_1.1fr]">
          <div className="lg:sticky lg:top-24 lg:self-start">
            <p className="eyebrow">How it works</p>
            <h2 id="how" className="mt-3 font-display text-2xl font-semibold tracking-tight sm:text-3xl">
              From question to cited answer
            </h2>
            <p className="mt-4 max-w-sm text-muted">
              The model only writes from passages it found. If nothing relevant turns up, you get a clear "I don't
              know".
            </p>
          </div>
          <ol className="steps relative space-y-12 pl-12">
            <span aria-hidden className="absolute bottom-2 left-[15px] top-2 w-px bg-white/10" />
            <span
              aria-hidden
              className="steps-rail-fill absolute bottom-2 left-[15px] top-2 w-px origin-top bg-gradient-to-b from-accent to-lime shadow-[0_0_12px_var(--color-accent)]"
            />
            {STEPS.map(([title, body], i) => (
              <li key={title} className="step relative">
                <span className="glass absolute -left-12 top-0 z-10 grid size-8 place-items-center rounded-full bg-ink-2 font-mono text-xs text-accent">
                  {i + 1}
                </span>
                <h3 className="font-semibold text-fg">{title}</h3>
                <p className="mt-1.5 max-w-md text-sm leading-relaxed text-muted">{body}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className="not-box glass mt-28 rounded-2xl p-6 text-sm">
          <h2 className="font-semibold text-amber-200">What AskMedi is not</h2>
          <p className="mt-1.5 leading-relaxed text-amber-50/75">
            It does not diagnose you, prescribe medicine or recommend a dose for you. It is not a therapist or a
            replacement for your doctor or pharmacist. {DISCLAIMER}
          </p>
        </section>
      </main>

      <footer className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 border-t border-line px-4 py-8 text-xs text-faint sm:px-6">
        <span className="flex items-center gap-2">
          <Mark className="size-4 text-accent" /> AskMedi
        </span>
        <span>Sources: MedlinePlus (NLM), openFDA, PubMed Central.</span>
      </footer>
    </div>
  )
}
