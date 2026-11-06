import { describe, expect, it } from "vitest";
import copy from "./content/storyPage.json";

// The build copies ../media into dist/media; listed by Vite so no Node typings are needed.
const mediaFiles = Object.keys(import.meta.glob(["../../media/*.{mp4,srt}", "../../media/posters/*.jpg"], { query: "?url" })).map((p) =>
  p.replace("../../media/", ""),
);

describe("video files", () => {
  it("has every video, poster and subtitle file the story page names", () => {
    for (const item of copy.videos.items) {
      for (const f of [item.src, item.poster, item.captions.replace(/\.vtt$/, ".srt")]) {
        expect(mediaFiles, f).toContain(f.replace(/^media\//, ""));
      }
    }
  });
});
