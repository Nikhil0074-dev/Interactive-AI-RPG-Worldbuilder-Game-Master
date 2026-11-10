"use client";
import { useEffect, useRef } from "react";

export function Modal({ title, onClose, children, testId, wide }: { title: string; onClose: () => void; children: React.ReactNode; testId?: string; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    ref.current?.focus();
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-40 flex items-end sm:items-center justify-center bg-black/70 p-0 sm:p-4" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={ref} tabIndex={-1} role="dialog" aria-modal="true" aria-label={title} data-testid={testId}
        className={`panel fade-in w-full ${wide ? "sm:max-w-4xl" : "sm:max-w-2xl"} max-h-[90vh] overflow-y-auto outline-none rounded-b-none sm:rounded-lg`}>
        <div className="sticky top-0 bg-panel flex items-center justify-between px-5 py-3 border-b border-edge z-10">
          <h2 className="text-xl text-gold">{title}</h2>
          <button className="btn" onClick={onClose} aria-label="Close">Close</button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

export function Bar({ value, max, color, label }: { value: number; max: number; color: string; label: string }) {
  const pct = max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0;
  return (
    <div>
      <div className="flex justify-between text-xs text-muted mb-1"><span>{label}</span><span>{value}/{max}</span></div>
      <div className="bar" role="progressbar" aria-valuenow={value} aria-valuemin={0} aria-valuemax={max} aria-label={label}>
        <div className="h-full transition-all duration-500" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}
