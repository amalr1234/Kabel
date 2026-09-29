export const SYSTEMS = ["SAP", "S/4HANA", "ABAP", "HANA", "NetWeaver", "Fiori", "CPI", "Other"];

export const CATEGORIES = [
  "authentication",
  "performance",
  "installation",
  "upgrade",
  "authorization",
  "backup",
  "transport",
  "basis",
];

export const PRIORITIES = ["low", "medium", "high", "critical"];

export const STORAGE_KEYS = {
  searchDraft: "solvia:search-draft",
  lastSolution: "solvia:last-solution",
} as const;
