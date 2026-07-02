import { useRef, useEffect, useCallback } from 'react';

function useAnimationFrame(callback) {
  const requestRef = useRef(null);
  const previousTimeRef = useRef(null);

  const animate = useCallback((time) => {
    if (previousTimeRef.current !== null) {
      const delta = time - previousTimeRef.current;
      callback(time, delta);
    }
    previousTimeRef.current = time;
    requestRef.current = requestAnimationFrame(animate);
  }, [callback]);

  useEffect(() => {
    requestRef.current = requestAnimationFrame(animate);
    return () => {
      if (requestRef.current) cancelAnimationFrame(requestRef.current);
    };
  }, [animate]);
}

export default function Marquee({
  className = '',
  reverse = false,
  pauseOnHover = false,
  children,
  speed = 50,
  vertical = false,
  repeat = 4,
}) {
  const containerRef = useRef(null);
  const contentRef = useRef(null);
  const sizeRef = useRef(null);
  const animX = useRef(0);
  const isPaused = useRef(false);

  useAnimationFrame((t, delta) => {
    if (!containerRef.current || !contentRef.current || !sizeRef.current) return;
    if (pauseOnHover && isPaused.current) return;

    const singleSize = vertical
      ? sizeRef.current.offsetHeight
      : sizeRef.current.offsetWidth;

    const style = window.getComputedStyle(contentRef.current);
    const gap = parseFloat(vertical ? style.rowGap || '0' : style.columnGap || '0');
    const loopDistance = singleSize + gap;
    const dx = (speed * delta) / 1000;
    const effectiveDx = reverse ? dx : -dx;
    animX.current += effectiveDx;

    if (Math.abs(animX.current) >= loopDistance) {
      animX.current = animX.current % loopDistance;
    }

    contentRef.current.style.transform = vertical
      ? `translateY(${animX.current}px)`
      : `translateX(${animX.current}px)`;
  });

  return (
    <div
      ref={containerRef}
      className={`group flex overflow-hidden p-2 [--gap:2rem] [gap:var(--gap)] ${vertical ? 'flex-col' : 'flex-row'} ${className}`}
      onMouseEnter={() => { if (pauseOnHover) isPaused.current = true; }}
      onMouseLeave={() => { if (pauseOnHover) isPaused.current = false; }}
    >
      <div
        ref={contentRef}
        className={`flex shrink-0 justify-around [gap:var(--gap)] ${vertical ? 'flex-col' : 'flex-row'}`}
      >
        {Array.from({ length: repeat }).map((_, i) => (
          <div key={i} ref={i === 0 ? sizeRef : null} className="flex gap-8">
            {children}
          </div>
        ))}
      </div>
    </div>
  );
}