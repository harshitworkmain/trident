import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import '@fontsource/ibm-plex-sans/latin-400.css';
import '@fontsource/ibm-plex-sans/latin-500.css';
import '@fontsource/ibm-plex-sans/latin-600.css';
import '@fontsource/ibm-plex-mono/latin-400.css';
import '@fontsource/ibm-plex-mono/latin-500.css';
import './styles/tokens.css';
import './styles/base.css';
import './styles/components.css';
import './styles/layout.css';
import App from './App';
import { startOutbox } from './features/public/offline';

/** Offline app shell (public/sw.js). Real production builds only: dev and the mock bundle never register it. */
function registerServiceWorker() {
  if (!import.meta.env.PROD || import.meta.env.VITE_MOCK === '1' || !('serviceWorker' in navigator)) return;
  const register = () => { navigator.serviceWorker.register('/sw.js', { scope: '/', updateViaCache: 'none' }).catch(() => { /* the site works without it */ }); };
  // After load, so precaching never competes with the first paint on a slow connection.
  if (document.readyState === 'complete') register();
  else window.addEventListener('load', register, { once: true });
}

async function boot() {
  // Statically false in a real build, so the mock chunk is never emitted or loaded.
  if (import.meta.env.VITE_MOCK === '1') await import('./mock');
  registerServiceWorker();
  startOutbox();
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}

void boot();
