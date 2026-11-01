/** A small queue that fetches frames in the background, a few at a time, with a visible count. */
export interface Preloader {
  /** Add URLs to the end of the queue. Ones already asked for are ignored. */
  request(urls: string[]): void;
  /** Move a URL to the front of the queue (and add it if it is new). */
  prioritize(url: string): void;
  /** Resolves when the URL has loaded, or rejects if it could not. Asks for it first if it is new. */
  whenReady(url: string): Promise<void>;
  /** How many of the URLs asked for so far have finished loading, and how many have failed. */
  progress(): { done: number; total: number; failed: number };
  /** Called after every change in progress. Returns a function that stops listening. */
  onChange(listener: () => void): () => void;
}

export function createPreloader(load: (url: string) => Promise<void>, concurrency = 2): Preloader {
  const jobs = new Map<string, Promise<void>>();
  const queue: string[] = [];
  const listeners = new Set<() => void>();
  let active = 0;
  let done = 0;
  let failed = 0;
  const resolvers = new Map<string, { resolve(): void; reject(e: unknown): void }>();

  const notify = (): void => listeners.forEach((l) => l());

  function add(url: string): Promise<void> {
    const known = jobs.get(url);
    if (known) return known;
    const job = new Promise<void>((resolve, reject) => resolvers.set(url, { resolve, reject }));
    // Whoever does not wait on a job should not trigger an unhandled rejection.
    job.catch(() => {});
    jobs.set(url, job);
    queue.push(url);
    return job;
  }

  function pump(): void {
    while (active < concurrency && queue.length) {
      const url = queue.shift()!;
      active += 1;
      load(url).then(
        () => {
          done += 1;
          resolvers.get(url)?.resolve();
        },
        (err: unknown) => {
          failed += 1;
          resolvers.get(url)?.reject(err);
        },
      ).finally(() => {
        active -= 1;
        notify();
        pump();
      });
    }
  }

  return {
    request(urls) {
      for (const u of urls) add(u);
      notify();
      pump();
    },
    prioritize(url) {
      add(url);
      const at = queue.indexOf(url);
      if (at > 0) {
        queue.splice(at, 1);
        queue.unshift(url);
      }
      pump();
    },
    whenReady(url) {
      const job = add(url);
      this.prioritize(url);
      return job;
    },
    progress: () => ({ done, total: jobs.size, failed }),
    onChange(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}
