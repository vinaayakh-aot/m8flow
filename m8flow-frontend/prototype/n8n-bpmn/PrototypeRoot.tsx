// PROTOTYPE — throwaway.
// Three variants of an n8n-styled BPMN designer, switchable via ?variant=,
// per the /prototype skill's UI-prototype convention. The macro layout
// (full-viewport canvas, properties panel fixed to the right quarter) is
// constant across all three — that part came pre-decided from the user's
// request. What's being judged is the add-node affordance and the
// properties-panel information hierarchy.
import React, { useState } from 'react';
import { PrototypeSwitcher } from './PrototypeSwitcher';
import { VariantA } from './variants/VariantA';
import { VariantB } from './variants/VariantB';
import { VariantC } from './variants/VariantC';
import './shared/n8n-theme.css';

const VARIANTS = [
  { key: 'A', name: 'Inline add-on-connection, accordion panel' },
  { key: 'B', name: 'Searchable rail + tabbed panel' },
  { key: 'C', name: 'Command palette (⌘K), flat panel' },
];

function readVariant(): string {
  const fromUrl = new URLSearchParams(window.location.search).get('variant');
  return fromUrl && VARIANTS.some((v) => v.key === fromUrl) ? fromUrl : 'A';
}

export function PrototypeRoot() {
  const [variant, setVariant] = useState(readVariant);

  function onChange(key: string) {
    setVariant(key);
    const url = new URL(window.location.href);
    url.searchParams.set('variant', key);
    window.history.replaceState(null, '', url.toString());
  }

  return (
    <>
      {variant === 'A' && <VariantA />}
      {variant === 'B' && <VariantB />}
      {variant === 'C' && <VariantC />}
      <PrototypeSwitcher variants={VARIANTS} current={variant} onChange={onChange} />
    </>
  );
}
