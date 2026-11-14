import { describe, expect, it, vi } from "vitest";
import { issueUrl } from "../lakeRequests";
import { loadMappedLakes, SOURCE_LABELS, watchThisLakeUrl } from "./mappedLakes";
import { mappedFixture } from "./mappedFixture";

const ok = (body: unknown) => vi.fn().mockResolvedValue(new Response(JSON.stringify(body)));

describe("loadMappedLakes", () => {
  it("reads a valid file", async () => {
    const f = await loadMappedLakes("x", ok(mappedFixture));
    expect(f!.lakes).toHaveLength(3);
    expect(f!.notice.odbl).toBe(mappedFixture.notice.odbl);
  });
  it("drops a malformed mapped lake only", async () => {
    const bad = [{ id: "bad", lon: "x" }, { ...mappedFixture.lakes[0], id: "m9", source: "other" }, null];
    const f = await loadMappedLakes("x", ok({ ...mappedFixture, lakes: [...mappedFixture.lakes, ...bad] }));
    expect(f!.lakes.map((l) => l.id)).toEqual(["m0001", "m0002", "m0003"]);
  });
  it("is null for a missing file, bad JSON, a bad shape or a failed fetch", async () => {
    expect(await loadMappedLakes("x", vi.fn().mockResolvedValue(new Response("nope", { status: 404 })))).toBeNull();
    expect(await loadMappedLakes("x", vi.fn().mockResolvedValue(new Response("not json")))).toBeNull();
    expect(await loadMappedLakes("x", ok({ version: 1, lakes: [] }))).toBeNull();
    expect(await loadMappedLakes("x", vi.fn().mockRejectedValue(new Error("offline")))).toBeNull();
  });
  it("gives up after the timeout", async () => {
    const slow = vi.fn((_u: unknown, init?: RequestInit) => new Promise<Response>((_r, rej) => init!.signal!.addEventListener("abort", () => rej(new Error("aborted")))));
    expect(await loadMappedLakes("x", slow as unknown as typeof fetch, 5)).toBeNull();
  });
});

describe("watchThisLakeUrl", () => {
  it("opens the lake-request form with the point", () => {
    const u = watchThisLakeUrl({ id: "m0001", lat: 36.1234, lon: 73.5, km2: 0.12, year: 2020, source: "hkhpk2020", suparco: null });
    expect(u).toBe(issueUrl({ name: "Mapped lake m0001", lat: "36.1234", lon: "73.5", source: "HKH-PK-2020 outline, 2020" }));
  });
  it("says undated for an outline with no year", () => {
    expect(decodeURIComponent(watchThisLakeUrl(mappedFixture.lakes[1]))).toContain("OpenStreetMap outline, undated");
    expect(SOURCE_LABELS.himag).toBe("Hi-MAG");
  });
});
