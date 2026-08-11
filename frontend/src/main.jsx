import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';

// signal.css first: it is the vendored design system, and app.css only adds what
// the DS does not define. Reversing this makes the POC's own rules lose.
import './signal.css';
import './app.css';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
