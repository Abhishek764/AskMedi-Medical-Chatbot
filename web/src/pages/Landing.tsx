import { ArrowRight, BookOpenCheck, CircleSlash, Quote, Siren } from 'lucide-react'
import type { CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { Backdrop, DISCLAIMER, Logo } from '../components/Layout'
import SpotlightCard from '../components/reactbits/SpotlightCard'

const POINTS = [
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

const SOURCES = [
  ['1,000+', 'MedlinePlus topics'],
  ['300+', 'FDA drug labels'],
  ['359', 'research reviews'],
]

const glassCard = {
  '--spotlight-card-surface': 'linear-gradient(180deg, rgb(255 255 255 / 0.06), rgb(255 255 255 / 0.025))',
} as CSSProperties

function Cite({ n }: { n: number }) {
  return (
    <sup className="ml-0.5 rounded-md bg-accent/15 px-1 py-px font-mono text-[10px] font-medium text-accent">{n}</sup>
  )
}

/** A static example of a real answer: the hero shows the product instead of describing it. */
function DemoAnswer() {
  return (
    <figure className="glass relative w-full max-w-md rounded-3xl p-5 [transform:perspective(1200px)_rotateY(-6deg)_rotateX(2deg)] sm:p-6">
      <p className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-md bg-accent px-4 py-2 text-sm font-medium text-accent-ink">
        What are the symptoms of dengue?
      </p>
      <blockquote className="mt-4 space-y-2 text-[0.9375rem] leading-relaxed text-fg/90">
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
      <span className="absolute -right-3 -top-3 rounded-full border border-line bg-ink-2 px-2.5 py-1 font-mono text-[10px] uppercase tracking-wider text-accent shadow-lg">
        2 sources
      </span>
    </figure>
  )
}

export default function Landing() {
  return (
    <div className="relative min-h-dvh overflow-x-clip">
      <Backdrop />
      <header className="mx-auto flex max-w-6xl items-center justify-between px-4 py-5 sm:px-6">
        <Logo />
        <nav className="flex items-center gap-2 text-sm">
          <Link to="/login" className="btn min-h-10 px-3 text-sm text-fg hover:bg-white/5">
            Sign in
          </Link>
          <Link to="/register" className="btn btn-primary min-h-10 px-4 text-sm">
            Get started
          </Link>
        </nav>
      </header>

      <main className="mx-auto max-w-6xl px-4 pb-20 sm:px-6">
        <section className="grid items-center gap-14 pt-10 lg:grid-cols-[1.15fr_1fr] lg:pt-20">
          <div className="animate-rise">
            <p className="eyebrow">Medical answers, sourced</p>
            <h1 className="mt-4 font-display text-[2.3rem] font-semibold leading-[1.1] tracking-tight sm:text-5xl xl:text-[3.5rem]">
              Health answers with the{' '}
              <span className="whitespace-nowrap">
                <span className="font-mono font-normal text-accent/70">[</span>
                <span className="bg-gradient-to-r from-accent to-sky bg-clip-text text-transparent">sources</span>
                <span className="font-mono font-normal text-accent/70">]</span>
              </span>{' '}
              showing.
            </h1>
            <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted">
              Ask about a condition, a symptom or a medicine. AskMedi answers in plain language from trusted medical
              sources and shows you where every sentence came from.
            </p>
            <div className="mt-9 flex flex-wrap items-center gap-3">
              <Link to="/register" className="btn btn-primary h-12 px-6 text-base">
                Ask your first question <ArrowRight className="size-4" aria-hidden />
              </Link>
              <Link to="/login" className="btn btn-ghost h-12 px-5 text-base">
                I have an account
              </Link>
            </div>
            <dl className="mt-12 flex flex-wrap gap-x-8 gap-y-4">
              {SOURCES.map(([n, label]) => (
                <div key={label}>
                  <dt className="sr-only">{label}</dt>
                  <dd className="font-display text-2xl font-semibold text-fg">{n}</dd>
                  <dd className="text-xs text-muted">{label}</dd>
                </div>
              ))}
            </dl>
          </div>
          <div className="flex justify-center animate-rise [animation-delay:120ms] lg:justify-end">
            <DemoAnswer />
          </div>
        </section>

        <section aria-labelledby="how" className="mt-28">
          <h2 id="how" className="font-display text-2xl font-semibold tracking-tight">
            Built to be checked, not trusted blindly
          </h2>
          <ul className="mt-8 grid gap-4 sm:grid-cols-2">
            {POINTS.map(({ icon: Icon, title, body }) => (
              <li key={title}>
                <SpotlightCard
                  className="h-full rounded-2xl p-6"
                  spotlightColor="rgba(94, 234, 212, 0.22)"
                  grain={0.08}
                  style={glassCard}
                >
                  <Icon className="size-5 text-accent" aria-hidden />
                  <h3 className="mt-4 font-semibold text-fg">{title}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-muted">{body}</p>
                </SpotlightCard>
              </li>
            ))}
          </ul>
        </section>

        <section className="mt-10 rounded-2xl border border-warn/25 bg-warn/[0.06] p-6 text-sm">
          <h2 className="font-semibold text-amber-200">What AskMedi is not</h2>
          <p className="mt-1.5 leading-relaxed text-amber-100/80">
            It does not diagnose you, prescribe medicine or recommend a dose for you. It is not a therapist or a
            replacement for your doctor or pharmacist. {DISCLAIMER}
          </p>
        </section>
      </main>
    </div>
  )
}
