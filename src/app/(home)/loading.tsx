import MainLayout from "@/components/layout/main-layout";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <MainLayout>
      <div className="space-y-10">
        {/* Hero */}
        <header className="space-y-5">
          <div className="space-y-2">
            <Skeleton className="h-10 w-40 sm:h-14 sm:w-56" />
            <Skeleton className="h-4 w-[92%] sm:w-[72%]" />
            <Skeleton className="h-4 w-[82%] sm:w-[58%]" />
          </div>
          <div className="flex flex-wrap gap-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-6 w-28 rounded-full" />
            ))}
          </div>
          <div className="flex flex-wrap gap-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-9 w-24 rounded-md" />
            ))}
          </div>
        </header>

        {/* Explore card */}
        <Card className="bg-card/60">
          <CardHeader className="pb-3">
            <Skeleton className="h-6 w-28" />
            <Skeleton className="h-4 w-64" />
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex flex-col md:flex-row md:items-center gap-2">
              <div className="flex flex-1 items-center gap-2">
                <Skeleton className="h-11 w-full" />
                <Skeleton className="h-11 w-28" />
              </div>
            </div>
            <div className="flex items-center gap-2 overflow-x-auto pb-1 -mx-1 px-1 sm:flex-wrap sm:overflow-visible sm:pb-0 sm:mx-0 sm:px-0">
              {Array.from({ length: 7 }).map((_, i) => (
                <Skeleton key={i} className="h-11 w-24 shrink-0" />
              ))}
            </div>
            <Skeleton className="h-4 w-72" />
          </CardContent>
        </Card>

        {/* KPI grid */}
        <div className="space-y-4">
          <div className="flex items-end justify-between gap-3">
            <div className="space-y-1">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-7 w-40" />
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 sm:gap-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Card key={i}>
                <CardHeader className="pb-2">
                  <Skeleton className="h-4 w-20" />
                </CardHeader>
                <CardContent className="pt-0 pb-3">
                  <Skeleton className="h-7 w-24" />
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* Latest feed */}
        <div className="space-y-3">
          <div className="flex items-end justify-between gap-3">
            <div className="space-y-1">
              <Skeleton className="h-3 w-24" />
              <Skeleton className="h-7 w-36" />
            </div>
            <Skeleton className="h-11 w-28" />
          </div>
          <Card>
            <CardContent className="p-0 divide-y">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="px-3 py-2.5 sm:px-4 sm:py-3 space-y-2">
                  <div className="flex items-center gap-2">
                    <Skeleton className="h-3 w-14" />
                    <Skeleton className="h-3 w-10" />
                    <Skeleton className="h-5 w-12 rounded-full" />
                  </div>
                  <Skeleton className="h-5 w-full" />
                  <Skeleton className="h-5 w-5/6" />
                </div>
              ))}
            </CardContent>
          </Card>
        </div>

        {/* By source */}
        <div className="space-y-3">
          <div className="space-y-1">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-7 w-32" />
            <Skeleton className="h-4 w-72" />
          </div>
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-14 w-full rounded-md" />
            ))}
          </div>
        </div>
      </div>
    </MainLayout>
  );
}
