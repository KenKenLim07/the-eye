import { ReactNode } from "react";
import MainLayout from "./main-layout";

interface NewsLayoutProps {
  children: ReactNode;
  className?: string;
  variant?: 'compact' | 'standard' | 'wide' | 'full';
}

export default function NewsLayout({ 
  children, 
  className = "", 
  variant = 'standard' 
}: NewsLayoutProps) {
  // Map variant to container size
  const containerSizeMap = {
    compact: 'sm' as const,    // 896px - For focused reading
    standard: 'md' as const,   // 1152px - Default news layout
    wide: 'lg' as const,       // 1280px - Wide news with sidebar
    full: 'full' as const,     // Full width - For hero sections
  };

  return (
    <MainLayout 
      className={className} 
      containerSize={containerSizeMap[variant]}
    >
      {children}
    </MainLayout>
  );
} 