import type { ChatEvent } from './types'

/**
 * Parse a text/event-stream body into ChatEvents. EventSource can't send an Authorization header
 * or a POST body, so the chat endpoint is read with fetch and parsed here.
 */
export async function* readEvents(body: ReadableStream<Uint8Array>): AsyncGenerator<ChatEvent> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done })
    let split = buffer.indexOf('\n\n')
    while (split !== -1) {
      const event = parseBlock(buffer.slice(0, split))
      buffer = buffer.slice(split + 2)
      if (event) yield event
      split = buffer.indexOf('\n\n')
    }
    if (done) {
      const last = parseBlock(buffer)
      if (last) yield last
      return
    }
  }
}

export function parseBlock(block: string): ChatEvent | null {
  let type = 'message'
  const data: string[] = []
  for (const line of block.replace(/\r/g, '').split('\n')) {
    if (line.startsWith('event:')) type = line.slice(6).trim()
    else if (line.startsWith('data:')) data.push(line.slice(5).trimStart())
  }
  if (data.length === 0) return null
  try {
    return { type, data: JSON.parse(data.join('\n')) } as ChatEvent
  } catch {
    return null
  }
}
