import { getAsyncLifecycle, defineConfigSchema } from "@openmrs/esm-framework";
import { configSchema } from "./config-schema";

const moduleName = "@clearmed/esm-clearmed-widget-app";

const options = {
  featureName: "clearmed-widget",
  moduleName,
};

export const importTranslation = require.context("../translations", false, /\.json$/, "lazy");

export function startupApp() {
  defineConfigSchema(moduleName, configSchema);
}

export const clearmedWidget = getAsyncLifecycle(() => import("./clearmed-widget.component"), options);
