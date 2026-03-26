import MainLayout from "@/components/layout/main-layout";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

type Props = {
  titleWidthClassName?: string;
  subtitleWidthClassName?: string;
  showBack?: boolean;
};

export default function ArticlesGridSkeleton({
  titleWidthClassName = "w-44",
  subtitleWidthClassName = "w-64",
  showBack = true,
}: Props) {
  return (
    <MainLayout containerSize="xl">
      <div className="space-y-6">
        <div className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="flex items-start gap-3 min-w-0">
              {showBack ? <Skeleton className="h-11 w-11 shrink-0 rounded-md" /> : null}
              <div className="space-y-2 min-w-0">
                <Skeleton className={`h-8 ${titleWidthClassName}`} />
                <Skeleton className={`h-4 ${subtitleWidthClassName}`} />
              </div>
            </div>
          </div>
          <div className="flex flex-col md:flex-row items-stretch gap-2">
            <Skeleton className="h-11 w-full md:w-56" />
            <Skeleton className="h-11 w-full" />
            <Skeleton className="h-11 w-28" />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i}>
              <CardHeader className="space-y-2">
                <Skeleton className="h-5 w-full" />
                <Skeleton className="h-4 w-3/4" />
              </CardHeader>
              <CardContent className="space-y-2">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-5/6" />
                <Skeleton className="h-4 w-4/6" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </MainLayout>
  );
}
