# 🎨 Layout System Documentation

## Overview

This document outlines the responsive layout system implemented for the Philippine News Aggregator project, following senior developer best practices for scalable, maintainable, and consistent design.

## 🏗️ Architecture Principles

### 1. **Component Composition Over Inline Styles**
- Extract layout logic into reusable components
- Avoid repeating layout classes across pages
- Single source of truth for spacing and container constraints

### 2. **Mobile-First Responsive Design**
- Start with mobile constraints, scale up for larger screens
- Progressive enhancement approach
- Consistent breakpoint usage across components

### 3. **Design System Consistency**
- Centralized spacing and sizing constants
- Predictable container widths for different content types
- Maintainable CSS variable system

## 📱 Responsive Breakpoints

```typescript
export const BREAKPOINTS = {
  sm: '640px',   // Small tablets
  md: '768px',   // Medium tablets
  lg: '1024px',  // Small desktops
  xl: '1280px',  // Large desktops
  '2xl': '1536px', // Extra large screens
} as const;
```

## 🎯 Layout Components

### MainLayout
**Purpose**: Base layout wrapper for all pages
**Features**:
- Responsive padding scaling
- Configurable container sizing
- Consistent spacing system

**Usage**:
```tsx
import MainLayout from "@/components/layout/main-layout";

export default function MyPage() {
  return (
    <MainLayout containerSize="lg">
      <YourContent />
    </MainLayout>
  );
}
```

### NewsLayout
**Purpose**: Specialized layout for news content
**Variants**:
- `compact` (896px) - Focused reading
- `standard` (1152px) - Default news layout
- `wide` (1280px) - Dashboard/admin panels
- `full` (100%) - Hero sections, galleries

**Usage**:
```tsx
import NewsLayout from "@/components/layout/news-layout";

export default function ArticlePage() {
  return (
    <NewsLayout variant="compact">
      <ArticleContent />
    </NewsLayout>
  );
}
```

## 📏 Spacing System

### Responsive Padding
```typescript
export const RESPONSIVE_PADDING = {
  mobile: 'px-4',       // 16px - Mobile default
  tablet: 'sm:px-6',    // 24px - Small tablets
  desktop: 'md:px-8',   // 32px - Medium screens
  wide: 'lg:px-12',     // 48px - Large screens
  xl: 'xl:px-16',       // 64px - Extra large screens
} as const;
```

**Why This Approach?**
- **Mobile-first**: Ensures content is readable on small screens
- **Progressive scaling**: Prevents cramped layouts on larger screens
- **Consistent rhythm**: Maintains visual hierarchy across breakpoints

### Container Sizing
```typescript
export const CONTAINER_SIZES = {
  sm: 'max-w-4xl',      // 896px - Reading focus
  md: 'max-w-6xl',      // 1152px - Standard content
  lg: 'max-w-7xl',      // 1280px - Wide content
  xl: 'max-w-screen-xl', // 1280px - Extra wide
  full: 'max-w-full',   // 100% width
} as const;
```

## 🔧 Implementation Details

### CSS Variables
The system uses CSS custom properties for consistent theming:
```css
:root {
  --radius: 0.625rem;
  --background: oklch(1 0 0);
  --foreground: oklch(0.141 0.005 285.823);
  /* ... more variables */
}
```

### Utility Functions
```typescript
// Generate responsive padding classes
export function getResponsivePadding() {
  return `${RESPONSIVE_PADDING.mobile} ${RESPONSIVE_PADDING.tablet} ${RESPONSIVE_PADDING.desktop} ${RESPONSIVE_PADDING.wide} ${RESPONSIVE_PADDING.xl}`;
}

// Get container size class
export function getContainerSize(size: keyof typeof CONTAINER_SIZES = 'lg') {
  return CONTAINER_SIZES[size];
}
```

## 📱 Mobile-First Strategy

### Why Mobile-First?
1. **Performance**: Mobile constraints force optimization
2. **Accessibility**: Ensures content works on all devices
3. **User Experience**: Mobile users are the majority
4. **Maintenance**: Easier to add features than remove them

### Implementation Pattern
```tsx
// ❌ Bad: Desktop-first approach
<div className="px-16 md:px-8 sm:px-4">

// ✅ Good: Mobile-first approach
<div className="px-4 sm:px-6 md:px-8 lg:px-12 xl:px-16">
```

## 🎨 Design System Integration

### TailwindCSS Integration
- Uses Tailwind's 4px grid system
- Leverages CSS custom properties for theming
- Consistent spacing scale across components

### Component Library (ShadCN UI)
- All UI components respect the layout system
- Consistent spacing and sizing
- Theme-aware components using CSS variables

## 🚀 Best Practices

### 1. **Layout Component Usage**
```tsx
// ✅ Good: Use layout components
<MainLayout>
  <PageContent />
</MainLayout>

// ❌ Bad: Inline layout classes
<main className="min-h-screen bg-background p-4">
  <div className="container mx-auto">
    <PageContent />
  </div>
</main>
```

### 2. **Responsive Design**
```tsx
// ✅ Good: Progressive enhancement
<div className="space-y-4 md:space-y-6 lg:space-y-8">

// ❌ Bad: Fixed spacing
<div className="space-y-8">
```

### 3. **Container Sizing**
```tsx
// ✅ Good: Appropriate container for content type
<NewsLayout variant="compact"> {/* For articles */}
<NewsLayout variant="wide">    {/* For dashboards */}
<NewsLayout variant="full">    {/* For hero sections */}
```

## 🔍 Testing & Validation

### Responsive Testing
- Test on multiple device sizes
- Verify padding scales appropriately
- Check container constraints work correctly

### Visual Consistency
- Ensure spacing rhythm is maintained
- Verify content doesn't feel cramped or too spread out
- Check alignment across breakpoints

## 📚 Related Files

- `src/components/layout/main-layout.tsx` - Base layout component
- `src/components/layout/news-layout.tsx` - News-specific layouts
- `src/lib/design-system.ts` - Design system constants
- `src/app/layout-demo/page.tsx` - Layout system demonstration

## 🎯 Future Enhancements

### Planned Features
- [ ] Layout presets for common page types
- [ ] Dynamic container sizing based on content
- [ ] Layout performance optimization
- [ ] Advanced responsive utilities

### Considerations
- **Performance**: Monitor layout shift and rendering performance
- **Accessibility**: Ensure layouts work with assistive technologies
- **Maintenance**: Keep layout system simple and predictable

---

**Note**: This layout system follows industry best practices and is designed to scale with the project's growth while maintaining consistency and developer experience. 