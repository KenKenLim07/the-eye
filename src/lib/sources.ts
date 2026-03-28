export const PH_SOURCES = [
  "GMA",
  "Rappler",
  "Inquirer",
  "Manila Times",
  "Philstar",
  "Sunstar",
  "Manila Bulletin",
  "ABS-CBN",
] as const;

export const PH_SOURCES_WITH_ALL = [
  { value: "all", label: "All Sources" },
  ...PH_SOURCES.map((s) => ({ value: s, label: s })),
] as const;

