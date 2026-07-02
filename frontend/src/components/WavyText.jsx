import { useEffect, useState } from 'react';

export default function WavyText({ text = '', className = '' }) {
  const [phase, setPhase] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setPhase(prev => prev + 0.1);
    }, 50);
    return () => clearInterval(interval);
  }, []);

  return (
    <h2 className={className}>
      {text.split('').map((char, i) => {
        const yOffset = Math.sin(phase + i * 0.3) * 10;
        return (
          <span
            key={i}
            className="inline-block"
            style={{
              transform: `translateY(${yOffset}px)`,
              transition: 'transform 0.3s ease',
            }}
          >
            {char === ' ' ? '\u00A0' : char}
          </span>
        );
      })}
    </h2>
  );
}