/**
 * Test helper: the declaration blocks of every rule whose selector list has `selector` as one of its selectors.
 * Comments are stripped and @media (and other at-rule) blocks are flattened. A selector list is split on commas
 * outside parentheses, so `:is(a, b)` stays whole.
 */
export function rulesFor(css: string, selector: string): string[] {
  const want = selector.replace(/\s+/g, " ").trim();
  const out: string[] = [];
  const flat = css.replace(/\/\*[\s\S]*?\*\//g, "");
  for (const chunk of flat.split("}")) {
    const open = chunk.lastIndexOf("{");
    if (open < 0) continue;
    // After flattening, an at-rule's own "@media (...) {" prefix sits in front of the first inner selector.
    const head = chunk.slice(0, open).replace(/@[^{]*\{/g, "");
    const list: string[] = [];
    let depth = 0;
    let cur = "";
    for (const ch of head) {
      if (ch === "(") depth++;
      if (ch === ")") depth--;
      if (ch === "," && depth === 0) {
        list.push(cur);
        cur = "";
      } else cur += ch;
    }
    list.push(cur);
    if (list.some((s) => s.replace(/\s+/g, " ").trim() === want)) out.push(chunk.slice(open + 1).trim());
  }
  return out;
}
