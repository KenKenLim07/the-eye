import { Badge } from "@/components/ui/badge";

type Item = {
  label: string;
  value: string;
};

export default function ActiveFilters({ items }: { items: Item[] }) {
  const safeItems = (items || []).filter((i) => i && i.label && i.value);
  if (safeItems.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-2" aria-label="Active filters">
      {safeItems.map((i) => (
        <Badge
          key={`${i.label}:${i.value}`}
          variant="secondary"
          className="h-7 px-2.5 u-mono text-[10px] uppercase tracking-widest"
          title={`${i.label}: ${i.value}`}
        >
          {i.label}: {i.value}
        </Badge>
      ))}
    </div>
  );
}

