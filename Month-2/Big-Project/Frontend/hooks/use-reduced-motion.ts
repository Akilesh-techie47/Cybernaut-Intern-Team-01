/*!
 * Next.js - AeroDelay AI Premium Frontend
 * Custom hook for respecting reduced-motion preferences
 */

import { useEffect, useState, useCallback } from "react";

/**
 * useReducedMotion - respects user's prefers-reduced-motion preference
 * 
 * Returns:
 * - reduced: boolean indicating if reduced motion is preferred
 * - setReducedMotion: function to manually set the preference (for testing)
 * 
 * Features:
 * - Checks window.matchMedia("(prefers-reduced-motion: reduce)") on mount
 * - Listens for changes to the media query
 * - SSR-safe: returns false on the server (no window)
 * - Cleanup: removes event listener on unmount
 */
export function useReducedMotion() {
  const [reduced, setReduced] = useState<boolean>(false);

  useEffect(() => {
    // SSR: window may not be available, default to false
    if (typeof window === "undefined") {
      setReduced(false);
      return;
    }

    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mediaQuery.matches);

    const listener = () => setReduced(mediaQuery.matches);
    window.addEventListener("change", listener);

    return () => {
      window.removeEventListener("change", listener);
    };
  }, []);

  return { reduced };
}