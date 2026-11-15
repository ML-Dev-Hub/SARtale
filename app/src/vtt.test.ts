import { describe, expect, it } from "vitest";
import { srtToVtt } from "./vtt";

// The shipped subtitle files, read as text by Vite so no Node typings are needed.
const srts = import.meta.glob("../../media/*.srt", { query: "?raw", import: "default", eager: true }) as Record<string, string>;

describe("srtToVtt", () => {
  it("adds the header, drops cue numbers and uses dots in times", () => {
    const srt = "1\r\n00:00:00,113 --> 00:00:05,558\r\nA glacial lake bursts.\r\n\r\n2\r\n00:00:06,019 --> 00:00:10,294\r\nTwo lines,\r\nof text.\r\n";
    expect(srtToVtt(srt)).toBe(
      "WEBVTT\n\n00:00:00.113 --> 00:00:05.558\nA glacial lake bursts.\n\n00:00:06.019 --> 00:00:10.294\nTwo lines,\nof text.\n",
    );
  });

  it("keeps commas in the caption text", () => {
    expect(srtToVtt("1\n00:00:01,000 --> 00:00:02,000\nCloud, or clear.\n")).toContain("Cloud, or clear.");
  });

  it("converts every cue of every shipped subtitle file", () => {
    expect(Object.keys(srts).length).toBe(4); // the two site videos and the 30 s and 60 s demos
    for (const srt of Object.values(srts)) {
      const blocks = srt.trim().split(/\r?\n\r?\n+/).length;
      const vtt = srtToVtt(srt);
      expect(vtt.startsWith("WEBVTT\n\n")).toBe(true);
      expect(vtt.match(/-->/g)?.length).toBe(blocks);
      expect(vtt).not.toMatch(/\d{2}:\d{2}:\d{2},\d{3}/);
    }
  });
});
