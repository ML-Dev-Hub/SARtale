/** True for a plain left-click: no modifier key, so the app routes it itself. Ctrl, Cmd, Shift, Alt and middle clicks are left to the browser (new tab or window). */
export function isPlainClick(e: MouseEvent): boolean {
  return e.button === 0 && !e.ctrlKey && !e.metaKey && !e.shiftKey && !e.altKey && !e.defaultPrevented;
}

/** Makes `a` route through `go` on a plain click, while its href still works for right-click, open in a new tab and middle-click. Returns the cleanup. */
export function wireNavLink(a: HTMLAnchorElement, go: () => void): () => void {
  const onClick = (e: MouseEvent): void => {
    if (!isPlainClick(e)) return;
    e.preventDefault();
    go();
  };
  a.addEventListener("click", onClick);
  return () => a.removeEventListener("click", onClick);
}
