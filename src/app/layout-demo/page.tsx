import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import MainLayout from "@/components/layout/main-layout";
import NewsLayout from "@/components/layout/news-layout";

export default function LayoutDemo() {
  return (
    <MainLayout>
      {/* Header */}
      <div className="text-center space-y-4">
        <h1 className="text-4xl font-extrabold tracking-tighter text-foreground">
          🎨 Layout System Demo
        </h1>
        <p className="text-xl text-muted-foreground">
          Demonstrating responsive design patterns and layout variants
        </p>
        <Badge variant="secondary" className="text-sm">
          Senior Dev Best Practices
        </Badge>
      </div>

      {/* Layout Variants Demo */}
      <div className="space-y-12">
        {/* Compact Layout */}
        <div className="space-y-4">
          <h2 className="text-2xl font-bold text-foreground">Compact Layout (max-w-4xl)</h2>
          <NewsLayout variant="compact">
            <Card>
              <CardHeader>
                <CardTitle>Focused Reading Experience</CardTitle>
                <CardDescription>
                  Perfect for article content, forms, and focused user experiences.
                  Container width: 896px max.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground">
                  This layout variant uses the &apos;sm&apos; container size, providing an optimal reading width
                  that prevents eye strain while maintaining content focus.
                </p>
              </CardContent>
            </Card>
          </NewsLayout>
        </div>

        {/* Standard Layout */}
        <div className="space-y-4">
          <h2 className="text-2xl font-bold text-foreground">Standard Layout (max-w-6xl)</h2>
          <NewsLayout variant="standard">
            <Card>
              <CardHeader>
                <CardTitle>Default News Layout</CardTitle>
                <CardDescription>
                  Balanced layout for news articles with sidebars and navigation.
                  Container width: 1152px max.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground">
                  The standard layout provides enough space for content while allowing room for
                  navigation elements, related articles, and user interface components.
                </p>
              </CardContent>
            </Card>
          </NewsLayout>
        </div>

        {/* Wide Layout */}
        <div className="space-y-4">
          <h2 className="text-2xl font-bold text-foreground">Wide Layout (max-w-7xl)</h2>
          <NewsLayout variant="wide">
            <Card>
              <CardHeader>
                <CardTitle>Wide Content with Sidebar</CardTitle>
                <CardDescription>
                  Spacious layout for dashboards, admin panels, and complex interfaces.
                  Container width: 1280px max.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground">
                  Wide layouts are ideal for applications that need to display multiple columns,
                  data tables, or complex user interfaces with plenty of breathing room.
                </p>
              </CardContent>
            </Card>
          </NewsLayout>
        </div>

        {/* Full Width Layout */}
        <div className="space-y-4">
          <h2 className="text-2xl font-bold text-foreground">Full Width Layout</h2>
          <NewsLayout variant="full">
            <Card>
              <CardHeader>
                <CardTitle>Full Width Content</CardTitle>
                <CardDescription>
                  Maximum width for hero sections, image galleries, and immersive experiences.
                  Container width: 100% of viewport.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground">
                  Full-width layouts are perfect for hero sections, image galleries, video players,
                  and any content that benefits from maximum screen real estate.
                </p>
              </CardContent>
            </Card>
          </NewsLayout>
        </div>
      </div>

      {/* Responsive Design Explanation */}
      <Card className="mt-8">
        <CardHeader>
          <CardTitle>📱 Responsive Design System</CardTitle>
          <CardDescription>
            How our layout system adapts across different screen sizes
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h3 className="font-semibold mb-2">Mobile-First Approach</h3>
              <ul className="text-sm text-muted-foreground space-y-1">
                <li>• Base padding: 16px (px-4)</li>
                <li>• Small tablets: 24px (sm:px-6)</li>
                <li>• Medium screens: 32px (md:px-8)</li>
                <li>• Large screens: 48px (lg:px-12)</li>
                <li>• XL screens: 64px (xl:px-16)</li>
              </ul>
            </div>
            <div>
              <h3 className="font-semibold mb-2">Container Constraints</h3>
              <ul className="text-sm text-muted-foreground space-y-1">
                <li>• Compact: 896px max (reading focus)</li>
                <li>• Standard: 1152px max (news layout)</li>
                <li>• Wide: 1280px max (dashboard)</li>
                <li>• Full: 100% width (hero sections)</li>
              </ul>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Back to Home */}
      <div className="text-center">
        <Button asChild>
          <Link href="/">← Back to Home</Link>
        </Button>
      </div>
    </MainLayout>
  );
} 