import { ReactNode } from "react";
import { getResponsivePadding, getContainerSize } from "@/lib/design-system";
import Footer from "./footer";

interface MainLayoutProps {
  children: ReactNode;
  className?: string;
  containerSize?: 'sm' | 'md' | 'lg' | 'xl' | 'full';
}

export default function MainLayout({ 
  children, 
  className = "", 
  containerSize = 'lg' 
}: MainLayoutProps) {
  return (
    <div className="min-h-screen bg-background flex flex-col">
      <main className={`flex-1 ${className}`}>
        {/* Responsive padding using design system constants */}
        <div className={getResponsivePadding()}>
          {/* Container with max-width constraints and responsive margins */}
          <div className={`mx-auto ${getContainerSize(containerSize)} space-y-8`}>
            {children}
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
} 