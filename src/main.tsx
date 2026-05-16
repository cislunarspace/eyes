import React from 'react';
import ReactDOM from 'react-dom/client';
import './styles.css';

function App() {
  return (
    <main className="shell">
      <section className="hero" aria-labelledby="title">
        <p className="eyebrow">Rust rewrite milestone M1</p>
        <h1 id="title">Eyes</h1>
        <p className="summary">
          The Tauri shell is running. Camera, posture detection, and reminders arrive in later milestones.
        </p>
      </section>
    </main>
  );
}

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
