/// <reference types="vite/client" />

// Allow importing plain CSS files for side effects,
// e.g. `import './App.css'` in TS/TSX modules.
declare module '*.css';

declare const __APP_VERSION__: string;
