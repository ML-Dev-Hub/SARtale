/**
 * Loads an image and rejects if it is missing or not an image. A successful load is remembered, so a frame that
 * the preloader has already fetched resolves at once when the map asks for it. Only the fact of the load is kept,
 * not the pixels: the browser's own cache holds the file, so memory stays small.
 */
const loaded = new Map<string, Promise<void>>();

export function loadImage(url: string): Promise<void> {
  const known = loaded.get(url);
  if (known) return known;
  const job = new Promise<void>((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      // Decode off the main thread where the browser can, so the first paint of the frame does not stall.
      const decoded = img.decode?.();
      if (decoded) decoded.then(() => resolve(), () => resolve());
      else resolve();
    };
    img.onerror = () => reject(new Error("image not found or unreadable"));
    img.src = url;
  });
  loaded.set(url, job);
  // A failed load is not remembered, so "Try again" really tries again.
  job.catch(() => loaded.delete(url));
  return job;
}

/** True once the image at this URL has loaded in this page. */
export function isLoaded(url: string): boolean {
  return loaded.has(url);
}
