import { useRef, useCallback } from 'react';

/**
 * Mouse-tracking 3D perspective tilt card.
 * Automatically pauses all transforms while any form element inside
 * the card is focused — preventing focus-stealing on keystrokes.
 */
export default function TiltCard({ children, className = '', style = {}, intensity = 10 }) {
  const cardRef = useRef(null);
  const glowRef = useRef(null);
  const rafRef = useRef(null);
  const isFocusedRef = useRef(false); // tracks whether a child input has focus

  // ── Reset to flat ──────────────────────────────────────────
  const resetTransform = useCallback(() => {
    if (!cardRef.current) return;
    cardRef.current.style.transform =
      'perspective(900px) rotateX(0deg) rotateY(0deg) scale3d(1,1,1)';
    cardRef.current.style.transition = 'transform 0.5s cubic-bezier(0.23,1,0.32,1)';
    if (glowRef.current) glowRef.current.style.background = 'transparent';
  }, []);

  // ── When a child input gains focus → lock card flat ────────
  const handleFocusIn = useCallback(() => {
    isFocusedRef.current = true;
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    resetTransform();
  }, [resetTransform]);

  // ── When all children lose focus → unlock tilt ─────────────
  const handleFocusOut = useCallback((e) => {
    // relatedTarget is the element receiving focus next.
    // If it's still inside the card, stay locked.
    if (cardRef.current && cardRef.current.contains(e.relatedTarget)) return;
    isFocusedRef.current = false;
  }, []);

  // ── Mouse move → apply tilt (only when not focused) ────────
  const handleMouseMove = useCallback((e) => {
    if (isFocusedRef.current) return;  // ← KEY FIX: skip while typing
    if (!cardRef.current) return;

    if (rafRef.current) cancelAnimationFrame(rafRef.current);

    rafRef.current = requestAnimationFrame(() => {
      if (isFocusedRef.current) return; // double-check inside rAF
      const rect = cardRef.current.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const dx = (e.clientX - cx) / (rect.width / 2);
      const dy = (e.clientY - cy) / (rect.height / 2);

      cardRef.current.style.transform =
        `perspective(900px) rotateX(${-dy * intensity}deg) rotateY(${dx * intensity}deg) scale3d(1.02,1.02,1.02)`;
      cardRef.current.style.transition = 'transform 0.08s ease-out';

      if (glowRef.current) {
        const gx = ((e.clientX - rect.left) / rect.width) * 100;
        const gy = ((e.clientY - rect.top) / rect.height) * 100;
        glowRef.current.style.background =
          `radial-gradient(circle at ${gx}% ${gy}%, rgba(56,189,248,0.1) 0%, transparent 65%)`;
      }
    });
  }, [intensity]);

  // ── Mouse leave → reset ─────────────────────────────────────
  const handleMouseLeave = useCallback(() => {
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    resetTransform();
  }, [resetTransform]);

  return (
    <div
      ref={cardRef}
      className={`tilt-card ${className}`}
      style={{ transformStyle: 'preserve-3d', willChange: 'transform', ...style }}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      onFocusCapture={handleFocusIn}   // capture phase catches all child focus
      onBlurCapture={handleFocusOut}   // capture phase catches all child blur
    >
      {/* Cursor glow overlay */}
      <div
        ref={glowRef}
        style={{
          position: 'absolute',
          inset: 0,
          borderRadius: 'inherit',
          pointerEvents: 'none',
          zIndex: 1,
          transition: 'background 0.15s ease',
        }}
      />
      <div style={{ position: 'relative', zIndex: 2 }}>
        {children}
      </div>
    </div>
  );
}
