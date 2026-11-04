import "@fontsource-variable/bricolage-grotesque/wdth.css";
import "./styles.css";
import { createUplotLakeChart } from "./chart";
import { createLakeLocator } from "./lakeLocator";
import { printBrief } from "./lakeBrief";
import { loadLakes } from "./lakes";
import { mountOrShowError } from "./startup";

const root = document.getElementById("app")!;

// Without lakes.json the views still mount and each says that the lake data is missing.
void loadLakes("data/lakes.json").then((lakes) =>
  mountOrShowError(root, {
    lakes,
    createLakeChart: createUplotLakeChart,
    createLakeLocator,
    onLakeBrief: (lake) => lakes && printBrief(lake, lakes),
  }),
);
