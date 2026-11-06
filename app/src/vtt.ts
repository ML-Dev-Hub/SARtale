/** Converts SubRip (.srt) captions to WebVTT, which the browser's <track> element reads. */
export function srtToVtt(srt: string): string {
  const cues = srt
    .replace(/^﻿/, "")
    .replace(/\r\n?/g, "\n")
    .trim()
    .split(/\n{2,}/)
    .map((block) => {
      const lines = block.split("\n");
      if (/^\d+$/.test(lines[0].trim())) lines.shift();
      if (lines.length > 0) lines[0] = lines[0].replace(/(\d{2}:\d{2}:\d{2}),(\d{3})/g, "$1.$2");
      return lines.join("\n");
    })
    .filter((cue) => cue.includes("-->"));
  return `WEBVTT\n\n${cues.join("\n\n")}\n`;
}
