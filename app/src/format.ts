/** Data paths in lakes.json are relative to data/. */
export function dataUrl(path: string): string {
  return `data/${path}`;
}

/** "2026-07-02" to "2 Jul 2026", without time zone shifts. */
export function formatDate(iso: string): string {
  const [y, mo, d] = iso.split("-").map(Number);
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${d} ${months[mo - 1]} ${y}`;
}
