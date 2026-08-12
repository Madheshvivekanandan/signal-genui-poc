/**
 * The entire backend contract. The only place `fetch` appears.
 *
 * Server-sent events are read over `fetch` rather than with `EventSource`,
 * because `EventSource` is GET-only and the inspect endpoint takes a POST body.
 * One parser for both keeps the two paths honest with each other.
 *
 * Three channels share the connection, told apart by the SSE `event:` name:
 *
 *   a2ui   a real A2UI v0.9 message, handed to the `MessageProcessor` verbatim.
 *          This module does not inspect it — the protocol owns its own shape.
 *   meta   this app's chrome: section subtitle, signal count, timings. Not A2UI,
 *          and deliberately not modelled as components.
 *   answer the review pane's prose, plus the id of the surface carrying any
 *          molecules the answer attached.
 *
 * A2UI is transport-agnostic — its own MIME type is `application/a2ui+json`
 * carrying newline-delimited messages. SSE carries the same objects one per
 * frame, which a browser reads without a custom protocol, so that is what the
 * backend speaks.
 */

const SSE_DELIMITER = '\n\n';

/**
 * Parse one SSE frame into an event name and payload.
 *
 * Returns null for a frame we cannot use — a comment/keepalive line, or data that
 * is not JSON. A malformed frame is skipped rather than thrown, so one bad write
 * upstream does not end an otherwise good stream.
 */
function parseFrame(frame) {
  let name = 'message';
  const dataLines = [];

  for (const line of frame.split('\n')) {
    if (line.startsWith(':')) continue; // comment / keepalive
    if (line.startsWith('event:')) name = line.slice(6).trim();
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim());
  }

  if (dataLines.length === 0) return null;

  try {
    return { name, payload: JSON.parse(dataLines.join('\n')) };
  } catch {
    console.error('unparseable SSE payload', dataLines);
    return null;
  }
}

/**
 * Read an SSE response, invoking `onEvent(name, payload)` per frame.
 *
 * Resolves when the server closes the stream. Rejects only on a transport
 * failure — callers treat a rejection as "the connection broke", which is
 * distinct from the backend reporting a failure inside a `meta` event.
 */
async function readEvents(response, onEvent, signal) {
  if (!response.ok) {
    throw new Error(`stream failed with status ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Frames arrive split across chunks at arbitrary boundaries; everything up
      // to the last delimiter is complete, and the remainder stays buffered.
      let boundary = buffer.indexOf(SSE_DELIMITER);
      while (boundary !== -1) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + SSE_DELIMITER.length);
        const parsed = parseFrame(frame);
        if (parsed) onEvent(parsed.name, parsed.payload);
        boundary = buffer.indexOf(SSE_DELIMITER);
      }

      if (signal?.aborted) break;
    }
  } finally {
    // An abandoned reader keeps the connection open; releasing it is what makes
    // an aborted stream actually stop costing tokens upstream.
    reader.releaseLock();
  }
}

/** Stream one document's analysis as A2UI messages, as the agent decides them. */
export async function streamOverview(documentKey, onEvent, signal) {
  const response = await fetch(
    `/api/sections/rfp-overview?document=${encodeURIComponent(documentKey)}`,
    { headers: { Accept: 'text/event-stream' }, signal },
  );
  await readEvents(response, onEvent, signal);
}

/** Ask the review agent about one inspected molecule. */
export async function streamInspect(
  { question, subject, history, document },
  onEvent,
  signal,
) {
  const response = await fetch('/api/inspect', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({ question, subject, history, document }),
    signal,
  });
  await readEvents(response, onEvent, signal);
}

/**
 * Fetch the documents this build can analyse, and which one is the default.
 *
 * Resolves to null on failure. The caller keeps whatever it already had rather
 * than emptying the picker — losing the list mid-demo would be worse than showing
 * a stale one.
 */
export async function fetchDocuments(signal) {
  try {
    const response = await fetch('/api/documents', { signal });
    if (!response.ok) return null;
    return await response.json();
  } catch (error) {
    if (error.name !== 'AbortError') console.error('could not load documents', error);
    return null;
  }
}

/**
 * Fetch the static header for one document.
 *
 * Resolves to null on any failure: the header is chrome, and a missing one should
 * degrade to the page still rendering its generated section, not to an error screen.
 */
export async function fetchRfpHeader(documentKey, signal) {
  try {
    const response = await fetch(`/api/rfp?document=${encodeURIComponent(documentKey)}`, {
      signal,
    });
    if (!response.ok) return null;
    return await response.json();
  } catch (error) {
    if (error.name !== 'AbortError') console.error('could not load RFP header', error);
    return null;
  }
}
