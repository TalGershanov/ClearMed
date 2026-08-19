import { Type } from "@openmrs/esm-framework";

export interface ConfigSchema {
  clearmedApiBaseUrl: string;
}

export const configSchema = {
  clearmedApiBaseUrl: {
    _type: Type.String,
    _default: "https://api.clearmed.example.com",
    _description: "Base URL of the external ClearMed FastAPI backend",
  },
};
