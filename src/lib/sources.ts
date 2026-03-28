export const PH_SOURCES = [
  "GMA",
  "ABS-CBN",
  "Inquirer",
  "Philstar",
  "Rappler",
  "Manila Bulletin",
  "Manila Times",
  "Sunstar",
] as const;

export const PH_SOURCES_WITH_ALL = [
  { value: "all", label: "All Sources" },
  ...PH_SOURCES.map((s) => ({ value: s, label: s })),
] as const;
