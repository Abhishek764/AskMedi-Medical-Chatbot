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
    <ol className="mt-3 space-y-1 border-t border-slate-200 pt-2 text-xs text-slate-600">
      {items.map((c) => (
        <li key={`${c.position}-${c.chunk_id}`} id={`cite-${c.position}`} className="flex gap-2">
          <span className="font-semibold text-teal-700">[{c.position}]</span>
          <span>
            {c.url ? (
              <a href={c.url} target="_blank" rel="noreferrer" className="underline hover:text-teal-800">
                {c.title}
              </a>
            ) : (
              c.title
            )}
            {c.section ? <span> › {c.section}</span> : null}
            <span className="text-slate-400"> · {SOURCE_LABEL[c.source] ?? c.source}</span>
          </span>
        </li>
      ))}
    </ol>
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
          <a key={i} href={`#cite-${m[1]}`} className="ml-0.5 align-super text-[10px] font-semibold text-teal-700">
            [{m[1]}]
          </a>
        ) : (
          <span key={i}>{part}</span>
        )
      })}
    </>
  )
}
