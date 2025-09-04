import { ReactNode } from "react";
import { getResponsivePadding, getContainerSize } from "@/lib/design-system";

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
    <main className={`min-h-screen bg-background ${className}`}>
      {/* Responsive padding using design system constants */}
      <div className={getResponsivePadding()}>
        {/* Container with max-width constraints and responsive margins */}
        <div className={`mx-auto ${getContainerSize(containerSize)} space-y-8`}>
          {children}
        </div>
      </div>
    </main>
  );
} 