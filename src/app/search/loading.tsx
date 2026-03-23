import MainLayout from "@/components/layout/main-layout";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <MainLayout containerSize="xl">
      <div className="space-y-6">
        {/* Search header */}
        <div className="space-y-4">
          <div className="flex items-start justify-between gap-3">
            <div className="space-y-2">
              <Skeleton className="h-8 w-44" />
              <Skeleton className="h-4 w-64" />
            </div>
            <Skeleton className="h-4 w-16" />
          </div>
          <div className="flex flex-col md:flex-row items-stretch gap-2">
            <Skeleton className="h-10 w-full md:w-56" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-28" />
          </div>
        </div>

        {/* Results grid */}
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

