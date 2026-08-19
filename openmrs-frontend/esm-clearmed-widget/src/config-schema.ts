import { Type } from "@openmrs/esm-framework";

export interface ConfigSchema {
  clearmedApiBaseUrl: string;
}

export const configSchema = {
  clearmedApiBaseUrl: {
    _type: Type.String,
    _default: "https://clearmed.duckdns.org",
    _description: "Base URL of the external ClearMed FastAPI backend",
  },
};
