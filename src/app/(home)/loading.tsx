import MainLayout from "@/components/layout/main-layout";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <MainLayout>
      <div className="space-y-8">
        {/* Header */}
        <header>
          <Skeleton className="h-10 w-72 sm:h-14 sm:w-[420px]" />
          <Skeleton className="h-4 w-80 sm:w-[520px] mt-2" />
        </header>

        {/* Control bar */}
        <div className="space-y-3">
          <div className="flex flex-col md:flex-row md:items-center gap-2">
            <div className="flex flex-1 items-center gap-2">
              <Skeleton className="h-11 w-full" />
              <Skeleton className="h-11 w-28" />
            </div>
            <Skeleton className="h-4 w-40" />
          </div>
          <div className="flex items-center gap-2 overflow-x-auto pb-1 -mx-1 px-1 sm:flex-wrap sm:overflow-visible sm:pb-0 sm:mx-0 sm:px-0">
            {Array.from({ length: 7 }).map((_, i) => (
              <Skeleton key={i} className="h-11 w-24 shrink-0" />
            ))}
          </div>
        </div>

        {/* KPI grid */}
        <div className="space-y-4">
          <div className="flex items-end justify-between gap-3">
            <div className="space-y-1">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-7 w-40" />
              <Skeleton className="h-4 w-56 sm:hidden" />
            </div>
            <Skeleton className="h-4 w-48 hidden sm:block" />
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
      </div>
    </MainLayout>
  );
}
