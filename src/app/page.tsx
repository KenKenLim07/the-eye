import MainLayout from "@/components/layout/main-layout";
import ArticleRowServer from "../components/articles/article-row-server";
import { fetchAllArticles } from "@/lib/articles";

export default async function Home() {
  // Fetch all articles server-side in parallel
  const articlesBySource = await fetchAllArticles(20);

  return (
    <MainLayout>
      <div className="space-y-8 mt-10">
        <div className="text-center space-y-2">
          <h1 className="text-3xl font-bold tracking-tight">Philippine News</h1>
          <p className="text-sm text-muted-foreground">Latest headlines aggregated from top PH news sources</p>
        </div>

        <div className="space-y-8">
          <ArticleRowServer 
            articles={articlesBySource["GMA"] || []} 
            title="GMA News" 
            sourceValue="GMA" 
          />
          <ArticleRowServer 
            articles={articlesBySource["Rappler"] || []} 
            title="Rappler" 
            sourceValue="Rappler" 
          />
          <ArticleRowServer 
            articles={articlesBySource["Inquirer"] || []} 
            title="Inquirer" 
            sourceValue="Inquirer" 
          />
          <ArticleRowServer 
            articles={articlesBySource["Philstar"] || []} 
            title="Philstar" 
            sourceValue="Philstar" 
          />
          <ArticleRowServer 
            articles={articlesBySource["Sunstar"] || []} 
            title="Sunstar" 
            sourceValue="Sunstar" 
          />
          <ArticleRowServer 
            articles={articlesBySource["Manila Bulletin"] || []} 
            title="Manila Bulletin" 
            sourceValue="Manila Bulletin" 
          />
        </div>
      </div>
    </MainLayout>
  );
}
