"use client";

import { useCallback, useRef, useState } from "react";

const MIN_SCALE = 1;
const MAX_SCALE = 4;
const STEP = 1.5;

type Point = { x: number; y: number };

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

/**
 * Zoom and pan an image in place: buttons, double-click, drag and pinch.
 * The page keeps scrolling normally until the image is actually zoomed.
 */
export function useZoom() {
  const [scale, setScale] = useState(1);
  const [offset, setOffset] = useState<Point>({ x: 0, y: 0 });
  const pointers = useRef(new Map<number, Point>());
  const pinch = useRef<{ distance: number; scale: number } | null>(null);
  const drag = useRef<{ start: Point; offset: Point } | null>(null);

  const limit = useCallback((next: Point, nextScale: number, element: HTMLElement | null): Point => {
    if (!element || nextScale <= 1) return { x: 0, y: 0 };
    const maxX = (element.clientWidth * (nextScale - 1)) / 2;
    const maxY = (element.clientHeight * (nextScale - 1)) / 2;
    return { x: clamp(next.x, -maxX, maxX), y: clamp(next.y, -maxY, maxY) };
  }, []);

  const stage = useRef<HTMLDivElement>(null);

  const zoomTo = useCallback((nextScale: number) => {
    const bounded = clamp(nextScale, MIN_SCALE, MAX_SCALE);
    setScale(bounded);
    setOffset(previous => limit(previous, bounded, stage.current));
  }, [limit]);

  const reset = useCallback(() => { setScale(1); setOffset({ x: 0, y: 0 }); }, []);

  const handlers = {
    onPointerDown: (event: React.PointerEvent<HTMLDivElement>) => {
      if ((event.target as HTMLElement).closest("button")) return;
      pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
      if (pointers.current.size === 2) {
        const [first, second] = [...pointers.current.values()];
        pinch.current = { distance: Math.hypot(first.x - second.x, first.y - second.y), scale };
        drag.current = null;
      } else if (scale > 1) {
        event.currentTarget.setPointerCapture(event.pointerId);
        drag.current = { start: { x: event.clientX, y: event.clientY }, offset };
      }
    },
    onPointerMove: (event: React.PointerEvent<HTMLDivElement>) => {
      if (!pointers.current.has(event.pointerId)) return;
      pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
      if (pointers.current.size === 2 && pinch.current) {
        const [first, second] = [...pointers.current.values()];
        const distance = Math.hypot(first.x - second.x, first.y - second.y);
        if (pinch.current.distance > 0) zoomTo(pinch.current.scale * (distance / pinch.current.distance));
      } else if (drag.current && scale > 1) {
        setOffset(limit({
          x: drag.current.offset.x + event.clientX - drag.current.start.x,
          y: drag.current.offset.y + event.clientY - drag.current.start.y,
        }, scale, stage.current));
      }
    },
    onPointerUp: (event: React.PointerEvent<HTMLDivElement>) => {
      pointers.current.delete(event.pointerId);
      if (pointers.current.size < 2) pinch.current = null;
      if (pointers.current.size === 0) drag.current = null;
    },
    onPointerCancel: (event: React.PointerEvent<HTMLDivElement>) => {
      pointers.current.delete(event.pointerId);
      pinch.current = null;
      drag.current = null;
    },
    onDoubleClick: (event: React.MouseEvent<HTMLDivElement>) => {
      if ((event.target as HTMLElement).closest("button")) return;
      if (scale > 1) reset(); else zoomTo(2.25);
    },
  };

  return {
    stage,
    scale,
    zoomed: scale > 1,
    canZoomIn: scale < MAX_SCALE,
    zoomIn: () => zoomTo(scale * STEP),
    zoomOut: () => zoomTo(scale / STEP),
    reset,
    handlers,
    style: { transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})` } as React.CSSProperties,
  };
}
