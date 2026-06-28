import React from 'react';
import ReactDOM from 'react-dom/client';
import './styles.css';

function App() {
  return (
    <main className="shell">
      <section className="hero" aria-labelledby="title">
        <p className="eyebrow">Rust 重写里程碑 M1</p>
        <h1 id="title">Eyes</h1>
        <p className="summary">
          Tauri 壳已运行。摄像头、姿态检测和提醒将在后续里程碑中加入。
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
