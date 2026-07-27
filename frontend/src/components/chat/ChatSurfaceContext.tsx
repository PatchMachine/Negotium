import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';

import type { SurfaceRequest } from './InlineSurface';

/**
 * Surfaces currently loaded into the chat thread.
 *
 * Lives above both the shell and the chat page so a sidebar click can load a
 * feature *into* the conversation instead of navigating away from it.
 */
type ChatSurfaceValue = {
  surfaces: SurfaceRequest[];
  pushSurface: (surface: SurfaceRequest) => void;
  closeSurface: (index: number) => void;
  clearSurfaces: () => void;
};

const ChatSurfaceContext = createContext<ChatSurfaceValue>({
  surfaces: [],
  pushSurface: () => {},
  closeSurface: () => {},
  clearSurfaces: () => {},
});

const MAX_SURFACES = 4;

export function ChatSurfaceProvider({ children }: { children: ReactNode }) {
  const [surfaces, setSurfaces] = useState<SurfaceRequest[]>([]);

  const pushSurface = useCallback((surface: SurfaceRequest) => {
    setSurfaces((current) => {
      // Re-opening the same screen should move it to the front, not stack a
      // duplicate copy of a heavy component.
      const deduped = current.filter((item) => item.component !== surface.component);
      return [surface, ...deduped].slice(0, MAX_SURFACES);
    });
  }, []);

  const closeSurface = useCallback((index: number) => {
    setSurfaces((current) => current.filter((_item, position) => position !== index));
  }, []);

  const clearSurfaces = useCallback(() => setSurfaces([]), []);

  const value = useMemo(
    () => ({ surfaces, pushSurface, closeSurface, clearSurfaces }),
    [surfaces, pushSurface, closeSurface, clearSurfaces],
  );

  return <ChatSurfaceContext.Provider value={value}>{children}</ChatSurfaceContext.Provider>;
}

export function useChatSurfaces(): ChatSurfaceValue {
  return useContext(ChatSurfaceContext);
}
