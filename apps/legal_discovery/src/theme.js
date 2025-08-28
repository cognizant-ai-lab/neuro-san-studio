export const theme = {
  colors: {
    background: 'var(--color-bg)',
    backgroundAlt: 'var(--color-bg-alt)',
    surface: 'var(--color-surface)',
    surfaceHover: 'var(--color-surface-hover)',
    accent: 'var(--color-accent)',
    text: 'var(--color-text)',
    textMuted: 'var(--color-text-muted)',
    border: 'var(--color-border)',
    accentScale: {
      100: 'var(--color-accent-100)',
      200: 'var(--color-accent-200)',
      300: 'var(--color-accent-300)',
      400: 'var(--color-accent-400)',
      500: 'var(--color-accent-500)',
      600: 'var(--color-accent-600)',
      700: 'var(--color-accent-700)',
      800: 'var(--color-accent-800)',
      900: 'var(--color-accent-900)'
    }
  },
  spacing: {
    xs: 'var(--space-xs)',
    sm: 'var(--space-sm)',
    md: 'var(--space-md)',
    lg: 'var(--space-lg)'
  },
  typography: {
    fontBase: 'var(--font-base)',
    sizeSm: 'var(--font-size-sm)',
    sizeMd: 'var(--font-size-md)',
    sizeLg: 'var(--font-size-lg)',
    weightNormal: 'var(--font-weight-normal)',
    weightBold: 'var(--font-weight-bold)'
  },
  effects: {
    glow: '0 0 8px var(--color-accent-glow)',
    glass: 'blur(var(--glass-blur))'
  }
};

export function applyDesignTokens(tokens) {
  const r = document.documentElement;
  const set = (k, v) => r.style.setProperty(k, v);
  const c = tokens.color || {};
  const e = tokens.effect || {};
  const f = tokens.font || {};
  // Core colors
  if (c.bg?.value) set('--color-bg', c.bg.value);
  if (c.bgAlt?.value) set('--color-bg-alt', c.bgAlt.value);
  if (c.surface?.value) set('--color-surface', c.surface.value);
  if (c.accent?.value) set('--color-accent', c.accent.value);
  if (c.text?.value) set('--color-text', c.text.value);
  if (c.textMuted?.value) set('--color-text-muted', c.textMuted.value);
  if (c.container?.value) set('--color-surface-hover', c.container.value);
  // Typography / spacing defaults
  if (f.base?.value) set('--font-base', f.base.value);
  set('--font-size-sm', '0.875rem');
  set('--font-size-md', '1rem');
  set('--font-size-lg', '1.125rem');
  set('--font-weight-normal', '400');
  set('--font-weight-bold', '700');
  set('--space-xs', '0.25rem');
  set('--space-sm', '0.5rem');
  set('--space-md', '1rem');
  set('--space-lg', '1.5rem');
  // Effects
  if (e.glow?.value) set('--color-accent-glow', c.accent?.value || '#00e5ff');
  if (e.glassBlur?.value) set('--glass-blur', e.glassBlur.value);
}
