import MainLayout from "@/components/layout/main-layout";
import ArticleRow from "../components/articles/article-row";

export default function Home() {
  return (
    <MainLayout>
      <div className="space-y-8 mt-10">
        <div className="text-center space-y-2">
          <h1 className="text-3xl font-bold tracking-tight">Philippine News</h1>
          <p className="text-sm text-muted-foreground">Latest headlines aggregated from top PH news sources</p>
        </div>

        <div className="space-y-8">
          <ArticleRow sourceValue="GMA News Online" title="GMA News" limit={20} />
          <ArticleRow sourceValue="Rappler" title="Rappler" limit={20} />
          <ArticleRow sourceValue="Philippine Daily Inquirer" title="Inquirer" limit={20} />
          <ArticleRow sourceValue="Philippine Star" title="Philstar" limit={20} />
          <ArticleRow sourceValue="Sunstar" title="Sunstar" limit={20} />
          <ArticleRow sourceValue="Manila Bulletin" title="Manila Bulletin" limit={20} />
        </div>
      </div>
    </MainLayout>
  );
}
