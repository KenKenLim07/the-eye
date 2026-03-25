import ArticlesGridSkeleton from "@/components/loading/articles-grid-skeleton";

export default function Loading() {
  return (
    <ArticlesGridSkeleton
      titleWidthClassName="w-48"
      subtitleWidthClassName="w-24"
      showBack={true}
    />
  );
}
