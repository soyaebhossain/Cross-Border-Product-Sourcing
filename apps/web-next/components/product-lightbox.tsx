"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { resolveImageUrl, type ResolvedProductMedia } from "../lib/api";
import { useLocale } from "../lib/locale-context";

const MIN_SCALE = 1;
const MAX_SCALE = 5;

type Point = { x: number; y: number };

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

/** Full-screen viewer with wheel, pinch, drag, double-click and keyboard zoom. */
export function ProductLightbox({
  media,
  name,
  startIndex,
  onClose,
}: {
  media: ResolvedProductMedia[];
  name: string;
  startIndex: number;
  onClose: () => void;
}) {
  const { locale } = useLocale();
  const bn = locale === "bn";
  const [index, setIndex] = useState(startIndex);
  const [scale, setScale] = useState(1);
  const [offset, setOffset] = useState<Point>({ x: 0, y: 0 });
  const stageRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const pointers = useRef(new Map<number, Point>());
  const pinch = useRef<{ distance: number; scale: number } | null>(null);
  const drag = useRef<{ start: Point; offset: Point } | null>(null);

  const current = media[clamp(index, 0, media.length - 1)];
  const src = resolveImageUrl(current.src) || "";

  const limitOffset = useCallback((next: Point, nextScale: number): Point => {
    const stage = stageRef.current;
    if (!stage || nextScale <= 1) return { x: 0, y: 0 };
    const maxX = (stage.clientWidth * (nextScale - 1)) / 2;
    const maxY = (stage.clientHeight * (nextScale - 1)) / 2;
    return { x: clamp(next.x, -maxX, maxX), y: clamp(next.y, -maxY, maxY) };
  }, []);

  const zoomTo = useCallback((nextScale: number) => {
    const bounded = clamp(nextScale, MIN_SCALE, MAX_SCALE);
    setScale(bounded);
    setOffset(previous => limitOffset(previous, bounded));
  }, [limitOffset]);

  const reset = useCallback(() => { setScale(1); setOffset({ x: 0, y: 0 }); }, []);
  const go = useCallback((step: number) => {
    setIndex(previous => (previous + step + media.length) % media.length);
    reset();
  }, [media.length, reset]);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    return () => {
      document.body.style.overflow = previousOverflow;
      previouslyFocused?.focus?.();
    };
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      else if (event.key === "+" || event.key === "=") zoomTo(scale * 1.4);
      else if (event.key === "-") zoomTo(scale / 1.4);
      else if (event.key === "0") reset();
      else if (event.key === "ArrowRight" && media.length > 1) go(1);
      else if (event.key === "ArrowLeft" && media.length > 1) go(-1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go, media.length, onClose, reset, scale, zoomTo]);

  // React registers wheel listeners as passive, so preventDefault needs a native listener.
  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      zoomTo(scale * (event.deltaY < 0 ? 1.15 : 1 / 1.15));
    };
    stage.addEventListener("wheel", onWheel, { passive: false });
    return () => stage.removeEventListener("wheel", onWheel);
  }, [scale, zoomTo]);

  const onPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId);
    pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (pointers.current.size === 2) {
      const [first, second] = [...pointers.current.values()];
      pinch.current = { distance: Math.hypot(first.x - second.x, first.y - second.y), scale };
      drag.current = null;
    } else {
      drag.current = { start: { x: event.clientX, y: event.clientY }, offset };
    }
  };

  const onPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!pointers.current.has(event.pointerId)) return;
    pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (pointers.current.size === 2 && pinch.current) {
      const [first, second] = [...pointers.current.values()];
      const distance = Math.hypot(first.x - second.x, first.y - second.y);
      if (pinch.current.distance > 0) zoomTo(pinch.current.scale * (distance / pinch.current.distance));
    } else if (drag.current && scale > 1) {
      setOffset(limitOffset({
        x: drag.current.offset.x + event.clientX - drag.current.start.x,
        y: drag.current.offset.y + event.clientY - drag.current.start.y,
      }, scale));
    }
  };

  const onPointerEnd = (event: React.PointerEvent<HTMLDivElement>) => {
    pointers.current.delete(event.pointerId);
    if (pointers.current.size < 2) pinch.current = null;
    if (pointers.current.size === 0) drag.current = null;
  };

  const percent = Math.round(scale * 100);
  // Rendered on <body> so no transformed or clipped ancestor can trap the fixed overlay.
  return createPortal(
    <div className="lightbox" role="dialog" aria-modal="true" aria-label={bn ? `${name} ছবি বড় করে দেখুন` : `${name} image viewer`}>
      <div className="lightbox__bar">
        <span className="lightbox__title">{name}{media.length > 1 ? ` · ${index + 1}/${media.length}` : ""}</span>
        <div className="lightbox__tools">
          <button type="button" onClick={() => zoomTo(scale / 1.4)} disabled={scale <= MIN_SCALE} aria-label={bn ? "ছোট করুন" : "Zoom out"}>−</button>
          <output aria-live="polite">{percent}%</output>
          <button type="button" onClick={() => zoomTo(scale * 1.4)} disabled={scale >= MAX_SCALE} aria-label={bn ? "বড় করুন" : "Zoom in"}>+</button>
          <button type="button" onClick={reset} disabled={scale === 1}>{bn ? "রিসেট" : "Reset"}</button>
          <button type="button" ref={closeRef} onClick={onClose} aria-label={bn ? "বন্ধ করুন" : "Close"}>✕</button>
        </div>
      </div>
      <div
        className={`lightbox__stage${scale > 1 ? " lightbox__stage--zoomed" : ""}`}
        ref={stageRef}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerEnd}
        onPointerCancel={onPointerEnd}
        onDoubleClick={() => (scale > 1 ? reset() : zoomTo(2.5))}
      >
        {/* A plain img keeps the original resolution available for zooming. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={src}
          alt={current.alt?.trim() || name}
          draggable={false}
          style={{ transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})` }}
        />
      </div>
      {media.length > 1 ? (
        <>
          <button className="lightbox__nav lightbox__nav--prev" type="button" onClick={() => go(-1)} aria-label={bn ? "আগের ছবি" : "Previous image"}>‹</button>
          <button className="lightbox__nav lightbox__nav--next" type="button" onClick={() => go(1)} aria-label={bn ? "পরের ছবি" : "Next image"}>›</button>
        </>
      ) : null}
      <p className="lightbox__hint">
        {bn ? "স্ক্রল বা দুই আঙুলে জুম, টেনে সরান, ডাবল-ক্লিকে বড়/ছোট, Esc চাপলে বন্ধ" : "Scroll or pinch to zoom, drag to pan, double-click to toggle, Esc to close"}
      </p>
    </div>,
    document.body,
  );
}
