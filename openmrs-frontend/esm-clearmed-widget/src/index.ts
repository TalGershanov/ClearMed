import { getAsyncLifecycle, getSyncLifecycle, defineConfigSchema } from "@openmrs/esm-framework";
import { configSchema } from "./config-schema";
import ClearmedDashboardLink from "./clearmed-dashboard-link.component";

const moduleName = "@clearmed/esm-clearmed-widget-app";

const options = {
  featureName: "clearmed-widget",
  moduleName,
};

export const importTranslation = require.context("../translations", false, /\.json$/, "lazy");

export function startupApp() {
  defineConfigSchema(moduleName, configSchema);
}

// The clickable, ClearMed-branded ("Start Visit" + logo) nav-link extension
// for the chart's dashboard sidebar. `clearmedWidget` (below) is the
// *content* shown once this link is active -- registering it directly on
// patient-chart-dashboard-slot without a `createDashboard`-style wrapper is
// what caused "Could not find a valid dashboard definition", so the content
// registration below is left untouched; only the link's own rendering is
// customized (see clearmed-dashboard-link.component.tsx for why it doesn't
// use `createDashboard` directly -- its `icon` prop can't show our logo).
export const clearmedWidgetDashboardLink = getSyncLifecycle(ClearmedDashboardLink, options);

export const clearmedWidget = getAsyncLifecycle(() => import("./clearmed-widget.component"), options);
