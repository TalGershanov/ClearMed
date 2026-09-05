import React, { useMemo } from "react";
import { BrowserRouter, useLocation } from "react-router-dom";
import { ConfigurableLink } from "@openmrs/esm-framework";
import { dashboardMeta } from "./dashboard.meta";
import logo from "./assets/logo-symbol.png";
import styles from "./clearmed-dashboard-link.scss";

// Mirrors @openmrs/esm-styleguide's `createDashboard`/`DashboardExtension`
// (nav-link active-state + navigation behavior), but renders the ClearMed
// logo instead of a built-in Carbon icon -- `createDashboard`'s `icon` prop
// only accepts a fixed set of built-in sprite names, it can't show an
// arbitrary logo image.
function ClearmedDashboardLinkContent({ basePath }: { basePath: string }) {
  const location = useLocation();
  const { path, title } = dashboardMeta;

  const isActive = useMemo(() => {
    const p = path.startsWith("/") ? path.slice(1) : path;
    const pathSegments = p.split("/").map((s) => decodeURIComponent(s));
    const localSegments = (location.pathname ?? "")
      .split("/")
      .slice(1)
      .map((s) => decodeURIComponent(s));
    return localSegments.some((_, i) => pathSegments.every((seg, j) => localSegments[i + j] === seg));
  }, [location.pathname, path]);

  const linkClassName = ["cds--side-nav__link", isActive ? "active-left-nav-link" : ""]
    .filter(Boolean)
    .join(" ");

  return (
    <div key={path}>
      <ConfigurableLink className={linkClassName} to={`${basePath}/${encodeURIComponent(path)}`}>
        <span className={styles.menu}>
          <img src={logo} alt="" className={styles.logo} />
          <span>{title}</span>
        </span>
      </ConfigurableLink>
    </div>
  );
}

export default function ClearmedDashboardLink({ basePath }: { basePath: string }) {
  return (
    <BrowserRouter>
      <ClearmedDashboardLinkContent basePath={basePath} />
    </BrowserRouter>
  );
}
