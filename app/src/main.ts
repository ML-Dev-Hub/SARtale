import "./styles.css";
import { createUplotLakeChart } from "./chart";
import { createLakeLocator } from "./lakeLocator";
import { printLatestBrief } from "./lakeBrief";
import { loadRequests } from "./lakeRequests";
import { loadLakes } from "./lakes";
import { mountOrShowError } from "./startup";

const root = document.getElementById("app")!;

// Say something at once, so a slow connection never shows a blank page.
root.textContent = "Loading SARtale…";

// The app waits only for lakes.json (bounded by a timeout); without it the views still mount and each says that the
// lake data is missing. The lake requests are fetched alongside and shown when they arrive: a slow or failed
// requests.json never holds up the page.
const requests = loadRequests();
void loadLakes("data/lakes.json").then((lakes) => {
  const app = mountOrShowError(root, {
    lakes,
    createLakeChart: createUplotLakeChart,
    createLakeLocator,
    requests: [],
    onLakeBrief: (lake) => {
      if (lakes) void printLatestBrief(lake, lakes);
    },
  });
  if (app) void requests.then((list) => app.setRequests(list));
});
