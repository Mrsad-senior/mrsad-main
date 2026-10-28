/** Minimal line diff (LCS) for comparing policy versions. */

export interface DiffLine {
  type: 'same' | 'add' | 'del';
  text: string;
  /** 1-based line number in the old text (absent for additions). */
  oldLine?: number;
  /** 1-based line number in the new text (absent for deletions). */
  newLine?: number;
}

export interface DiffStats {
  added: number;
  removed: number;
}

/** Larger inputs fall back to a prefix/suffix trim so the UI never hangs on huge documents. */
const MAX_CELLS = 4_000_000;

export function splitLines(text: string): string[] {
  if (text === '') return [];
  const lines = text.replace(/\r\n?/g, '\n').split('\n');
  if (lines[lines.length - 1] === '') lines.pop();
  return lines;
}

export function lineDiff(oldText: string, newText: string): DiffLine[] {
  const a = splitLines(oldText);
  const b = splitLines(newText);

  // Trim common prefix/suffix: cheap and keeps the LCS table small for typical edits.
  let prefix = 0;
  while (prefix < a.length && prefix < b.length && a[prefix] === b[prefix]) prefix++;
  let suffix = 0;
  while (
    suffix < a.length - prefix &&
    suffix < b.length - prefix &&
    a[a.length - 1 - suffix] === b[b.length - 1 - suffix]
  ) suffix++;

  const out: DiffLine[] = [];
  for (let i = 0; i < prefix; i++) out.push({ type: 'same', text: a[i], oldLine: i + 1, newLine: i + 1 });

  const midA = a.slice(prefix, a.length - suffix);
  const midB = b.slice(prefix, b.length - suffix);
  if (midA.length * midB.length > MAX_CELLS) {
    midA.forEach((text, i) => out.push({ type: 'del', text, oldLine: prefix + i + 1 }));
    midB.forEach((text, j) => out.push({ type: 'add', text, newLine: prefix + j + 1 }));
  } else {
    out.push(...lcsDiff(midA, midB, prefix));
  }

  for (let k = suffix; k > 0; k--) {
    const ai = a.length - k;
    const bi = b.length - k;
    out.push({ type: 'same', text: a[ai], oldLine: ai + 1, newLine: bi + 1 });
  }
  return out;
}

function lcsDiff(a: string[], b: string[], offset: number): DiffLine[] {
  const n = a.length;
  const m = b.length;
  // table[i][j] = LCS length of a[i:] and b[j:]
  const table: Uint32Array[] = Array.from({ length: n + 1 }, () => new Uint32Array(m + 1));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      table[i][j] = a[i] === b[j] ? table[i + 1][j + 1] + 1 : Math.max(table[i + 1][j], table[i][j + 1]);
    }
  }
  const out: DiffLine[] = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      out.push({ type: 'same', text: a[i], oldLine: offset + i + 1, newLine: offset + j + 1 });
      i++;
      j++;
    } else if (table[i + 1][j] >= table[i][j + 1]) {
      out.push({ type: 'del', text: a[i], oldLine: offset + i + 1 });
      i++;
    } else {
      out.push({ type: 'add', text: b[j], newLine: offset + j + 1 });
      j++;
    }
  }
  for (; i < n; i++) out.push({ type: 'del', text: a[i], oldLine: offset + i + 1 });
  for (; j < m; j++) out.push({ type: 'add', text: b[j], newLine: offset + j + 1 });
  return out;
}

export function diffStats(lines: DiffLine[]): DiffStats {
  let added = 0;
  let removed = 0;
  for (const line of lines) {
    if (line.type === 'add') added++;
    else if (line.type === 'del') removed++;
  }
  return { added, removed };
}
