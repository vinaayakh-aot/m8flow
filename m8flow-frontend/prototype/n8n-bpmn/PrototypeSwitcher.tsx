// PROTOTYPE — throwaway. Floating bottom-centre variant switcher, per the
// /prototype skill's UI-prototype convention. Gated on dev builds only so a
// stray merge can't ship it.
import React, { useEffect } from 'react';

export type VariantDef = { key: string; name: string };

type Props = {
  variants: VariantDef[];
  current: string;
  onChange: (key: string) => void;
};

export function PrototypeSwitcher({ variants, current, onChange }: Props) {
  const index = variants.findIndex((v) => v.key === current);
  const active = variants[index] ?? variants[0];

  const step = (delta: number) => {
    const next = (index + delta + variants.length) % variants.length;
    onChange(variants[next].key);
  };

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const tag = target?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || target?.isContentEditable) return;
      if (event.key === 'ArrowLeft') step(-1);
      if (event.key === 'ArrowRight') step(1);
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index]);

  if (import.meta.env.PROD) return null;

  return (
    <div className="prototype-switcher">
      <button type="button" onClick={() => step(-1)} aria-label="Previous variant">
        ←
      </button>
      <span>
        {active.key} — {active.name}
      </span>
      <button type="button" onClick={() => step(1)} aria-label="Next variant">
        →
      </button>
    </div>
  );
}
