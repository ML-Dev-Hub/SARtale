import "./styles.css";
import { createUplotLakeChart } from "./chart";
import { createLakeLocator } from "./lakeLocator";
import { printBrief } from "./lakeBrief";
import { loadRequests } from "./lakeRequests";
import { loadLakes } from "./lakes";
import { mountOrShowError } from "./startup";

const root = document.getElementById("app")!;

// Without lakes.json the views still mount and each says that the lake data is missing.
void Promise.all([loadLakes("data/lakes.json"), loadRequests()]).then(([lakes, requests]) =>
  mountOrShowError(root, {
    lakes,
    createLakeChart: createUplotLakeChart,
    createLakeLocator,
    requests,
    onLakeBrief: (lake) => lakes && printBrief(lake, lakes),
  }),
);
