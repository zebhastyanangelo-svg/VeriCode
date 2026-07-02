import { useRef, useEffect, useState } from 'react';

export default function ScrollReveal({ children, className = '', delay = 0, direction = 'up' }) {
  const ref = useRef(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setTimeout(() => setVisible(true), delay);
          obs.unobserve(el);
        }
      },
      { threshold: 0.1 }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [delay]);

  const dirStyles = {
    up: { transform: visible ? 'translateY(0)' : 'translateY(40px)', opacity: visible ? 1 : 0 },
    down: { transform: visible ? 'translateY(0)' : 'translateY(-40px)', opacity: visible ? 1 : 0 },
    left: { transform: visible ? 'translateX(0)' : 'translateX(40px)', opacity: visible ? 1 : 0 },
    right: { transform: visible ? 'translateX(0)' : 'translateX(-40px)', opacity: visible ? 1 : 0 },
    scale: { transform: visible ? 'scale(1)' : 'scale(0.85)', opacity: visible ? 1 : 0 },
  };

  return (
    <div
      ref={ref}
      className={className}
      style={{
        transition: 'all 0.7s cubic-bezier(0.16, 1, 0.3, 1)',
        ...dirStyles[direction],
      }}
    >
      {children}
    </div>
  );
}