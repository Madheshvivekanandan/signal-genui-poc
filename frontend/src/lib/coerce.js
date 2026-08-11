/**
 * Coercers for molecule payloads.
 *
 * Everything a molecule renders came out of a language model. A null where a
 * string belongs, a number where a string belongs, or a missing array is
 * expected input here, not an exceptional case — the backend's schema catches
 * shape, but these catch the residue and keep a single bad field from throwing
 * mid-render.
 *
 * Read every payload field through one of these. Never index into
 * `molecule.metrics[0].label` directly.
 */

/** Coerce to a trimmed display string. Objects and arrays collapse to empty. */
export function str(value, fallback = '') {
  if (typeof value === 'string') return value.trim();
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  return fallback;
}

/** Coerce to an array. Anything non-array becomes empty. */
export function arr(value) {
  return Array.isArray(value) ? value : [];
}

/** Coerce to a boolean, treating absent as false. */
export function bool(value) {
  return value === true;
}

/**
 * Pick a value from a closed set of allowed options.
 *
 * Used for the design system's variant axes — callout tone, score band — where
 * an unrecognised value must fall back to the neutral variant rather than
 * producing a molecule with no styling at all.
 */
export function oneOf(value, allowed, fallback) {
  return allowed.includes(value) ? value : fallback;
}

/**
 * Build the class list for a molecule's shared capabilities.
 *
 * DS §3: most molecules can wear `.inspect` (clickable datapoint) and `.signal`
 * (joins the review queue). Both are additive on top of the molecule's own
 * class, and `.signal` is what turns a band coral, so the order matters to the
 * cascade — the design system's own selectors are written `.intel-card.inspect.signal`.
 */
export function capabilityClasses(base, molecule) {
  const classes = [base];
  if (bool(molecule.inspect)) classes.push('inspect');
  if (bool(molecule.signal)) classes.push('signal');
  return classes.join(' ');
}
