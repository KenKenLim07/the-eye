// Design System Constants
// Following senior dev best practices for consistent spacing and responsive design

export const SPACING = {
  // Base spacing units (4px grid system)
  xs: '1',      // 4px
  sm: '2',      // 8px
  md: '4',      // 16px
  lg: '6',      // 24px
  xl: '8',      // 32px
  '2xl': '12',  // 48px
  '3xl': '16',  // 64px
} as const;

export const CONTAINER_SIZES = {
  // Max-width constraints for different content types
  sm: 'max-w-4xl',      // 896px - Narrow content
  md: 'max-w-6xl',      // 1152px - Standard content
  lg: 'max-w-7xl',      // 1280px - Wide content (default)
  xl: 'max-w-screen-xl', // 1280px - Extra wide
  full: 'max-w-full',   // Full width
} as const;

export const RESPONSIVE_PADDING = {
  // Mobile-first responsive padding
  mobile: 'px-2',       // 16px on mobile
  tablet: 'sm:px-6',    // 24px on small tablets
  desktop: 'md:px-8',   // 32px on medium screens
  wide: 'lg:px-12',     // 48px on large screens
  xl: 'xl:px-16',       // 64px on extra large screens
} as const;

export const BREAKPOINTS = {
  // Tailwind breakpoints for reference
  sm: '640px',
  md: '768px',
  lg: '1024px',
  xl: '1280px',
  '2xl': '1536px',
} as const;

// Utility function to generate responsive padding classes
export function getResponsivePadding() {
  return `${RESPONSIVE_PADDING.mobile} ${RESPONSIVE_PADDING.tablet} ${RESPONSIVE_PADDING.desktop} ${RESPONSIVE_PADDING.wide} ${RESPONSIVE_PADDING.xl}`;
}

// Utility function to get container size class
export function getContainerSize(size: keyof typeof CONTAINER_SIZES = 'lg') {
  return CONTAINER_SIZES[size];
} 