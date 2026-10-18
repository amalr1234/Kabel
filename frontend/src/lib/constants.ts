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

export const SUPPORT_LEVELS = ["L1", "L2", "L3"] as const;

export const SUPPORT_LEVEL_LABELS: Record<(typeof SUPPORT_LEVELS)[number], string> = {
  L1: "L1 · Service desk",
  L2: "L2 · Application support",
  L3: "L3 · Basis / expert",
};

export const STORAGE_KEYS = {
  searchDraft: "solvia:search-draft",
  lastSolution: "solvia:last-solution",
} as const;
