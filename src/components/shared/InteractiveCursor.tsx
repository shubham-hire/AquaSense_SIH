import React, { useEffect, useState } from 'react';

/** A subtle sonar-style cursor halo; disabled automatically on touch devices. */
export const InteractiveCursor: React.FC = () => {
  const [pointer, setPointer] = useState({ x: -100, y: -100, active: false });

  useEffect(() => {
    if (!window.matchMedia('(pointer: fine)').matches) return;
    const move = (event: PointerEvent) => setPointer({ x: event.clientX, y: event.clientY, active: true });
    const leave = () => setPointer((current) => ({ ...current, active: false }));
    window.addEventListener('pointermove', move, { passive: true });
    document.documentElement.addEventListener('mouseleave', leave);
    return () => {
      window.removeEventListener('pointermove', move);
      document.documentElement.removeEventListener('mouseleave', leave);
    };
  }, []);

  return (
    <div
      aria-hidden="true"
      className={`cursor-sonar ${pointer.active ? 'opacity-100' : 'opacity-0'}`}
      style={{ transform: `translate3d(${pointer.x}px, ${pointer.y}px, 0)` }}
    >
      <span className="cursor-sonar__core" />
      <span className="cursor-sonar__ring" />
    </div>
  );
};
