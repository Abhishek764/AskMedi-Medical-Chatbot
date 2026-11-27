import type { Citation } from '../api/types'

const SOURCE_LABEL: Record<string, string> = {
  medlineplus: 'MedlinePlus (NLM)',
  openfda: 'FDA drug label',
  pmc: 'Research review (PMC)',
  local: 'Reference',
}

export function Citations({ items }: { items: Citation[] }) {
  if (items.length === 0) return null
  return (
    <div className="mt-4 border-t border-line pt-3">
      <p className="eyebrow text-faint">Sources</p>
      <ol className="mt-2 grid gap-1 text-xs">
        {items.map((c) => (
          <li
            key={`${c.position}-${c.chunk_id}`}
            id={`cite-${c.position}`}
            className="flex scroll-mt-24 gap-2.5 rounded-lg px-2 py-1.5 transition-colors target:bg-accent/10 hover:bg-white/[0.04]"
          >
            <span className="font-mono font-medium text-accent">[{c.position}]</span>
            <span className="min-w-0 text-muted">
              {c.url ? (
                <a
                  href={c.url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-fg/90 underline decoration-white/20 underline-offset-2 hover:text-accent hover:decoration-accent"
                >
                  {c.title}
                </a>
              ) : (
                <span className="text-fg/90">{c.title}</span>
              )}
              {c.section ? <span> › {c.section}</span> : null}
              <span className="font-mono text-[10px] uppercase tracking-wide text-faint">
                {' '}
                · {SOURCE_LABEL[c.source] ?? c.source}
              </span>
            </span>
          </li>
        ))}
      </ol>
    </div>
  )
}

/** Render "text [1] more [2]" with citation markers as superscript links. */
export function WithMarkers({ text }: { text: string }) {
  const parts = text.split(/(\[\d+\])/g)
  return (
    <>
      {parts.map((part, i) => {
        const m = /^\[(\d+)\]$/.exec(part)
        return m ? (
          <a
            key={i}
            href={`#cite-${m[1]}`}
            aria-label={`Source ${m[1]}`}
            className="ml-0.5 rounded-md bg-accent/15 px-1 py-px align-super font-mono text-[10px] font-medium text-accent transition hover:bg-accent hover:text-accent-ink"
          >
            {m[1]}
          </a>
        ) : (
          <span key={i}>{part}</span>
        )
      })}
    </>
  )
}
