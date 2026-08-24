import { getAsyncLifecycle, getSyncLifecycle, defineConfigSchema } from "@openmrs/esm-framework";
import { createDashboard } from "@openmrs/esm-styleguide";
import { configSchema } from "./config-schema";
import { dashboardMeta } from "./dashboard.meta";

const moduleName = "@clearmed/esm-clearmed-widget-app";

const options = {
  featureName: "clearmed-widget",
  moduleName,
};

export const importTranslation = require.context("../translations", false, /\.json$/, "lazy");

export function startupApp() {
  defineConfigSchema(moduleName, configSchema);
}

// The clickable, Carbon-styled nav-link extension for the chart's dashboard
// sidebar. `clearmedWidget` (below) is the *content* shown once this link is
// active -- registering it directly on patient-chart-dashboard-slot without
// this wrapper is what caused "Could not find a valid dashboard definition".
export const clearmedWidgetDashboardLink = getSyncLifecycle(createDashboard({ ...dashboardMeta }), options);

export const clearmedWidget = getAsyncLifecycle(() => import("./clearmed-widget.component"), options);
