import { useEffect, useState } from 'react';
import { ANDROID_APK_URL, APP_STORE_URL, APP_VERSION, PLAY_STORE_URL } from './config';
import PremiumFruitStudio from './components/PremiumFruitStudio';

function DownloadIcon() {
  return (
    <svg className="buttonIcon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M12 3.25a1 1 0 0 1 1 1v7.34l2.47-2.47a1 1 0 1 1 1.41 1.42l-4.18 4.18a1 1 0 0 1-1.4 0L7.1 10.54a1 1 0 1 1 1.41-1.42L11 11.58V4.25a1 1 0 0 1 1-1ZM5.75 16.5a1 1 0 0 1 1 1v1.25c0 .14.11.25.25.25h10c.14 0 .25-.11.25-.25V17.5a1 1 0 1 1 2 0v1.25A2.25 2.25 0 0 1 17 21H7a2.25 2.25 0 0 1-2.25-2.25V17.5a1 1 0 0 1 1-1Z" />
    </svg>
  );
}

export default function App() {
  // PWA install prompt handling
  useEffect(() => {
    function beforeInstall(e: any) {
      e.preventDefault();
      (window as any).__wfDeferredPrompt = e;
    }
    window.addEventListener('beforeinstallprompt', beforeInstall as EventListener);
    return () => window.removeEventListener('beforeinstallprompt', beforeInstall as EventListener);
  }, []);

  function promptInstall() {
    const deferred = (window as any).__wfDeferredPrompt;
    if (!deferred) return;
    deferred.prompt();
    deferred.userChoice.then(() => {
      (window as any).__wfDeferredPrompt = null;
    });
  }
  return (
    <>
      <header className="studio-topbar">
        <div className="studio-brand">
          <span className="topbarDot" />
          <span>WallFruits Studio</span>
        </div>
        <div className="studio-topbarCenter">
          <span className="studio-badge">Cadastro premium</span>
          <span className="studio-topbarText">Frutas, produtos agrícolas e anúncios com UX cinematográfica</span>
        </div>
        <div className="studio-topbarRight">
          <span className="studio-version">v{APP_VERSION}</span>
          <button className="studio-iconButton" onClick={promptInstall} type="button">
            Instalar
          </button>
        </div>
      </header>
      <main className="studio-shell">
        <aside className="studio-sidebar">
          <div className="studio-orb studio-orbOne" />
          <div className="studio-orb studio-orbTwo" />
          <div className="studio-sidebarContent">
            <div className="studio-eyebrow">WallFruits premium form system</div>
            <h1>Cadastro de frutas com presença de produto de luxo.</h1>
            <p>
              Uma experiência responsiva, cinematográfica e altamente refinada para registrar produtos agrícolas com
              foco em conversão, clareza e performance.
            </p>
            <div className="studio-chipRow">
              <span className="studio-chip">GPU first</span>
              <span className="studio-chip">Glass blur</span>
              <span className="studio-chip">60 FPS</span>
              <span className="studio-chip">Auto validate</span>
            </div>
            <div className="studio-linkRow">
              <a href={ANDROID_APK_URL}>APK Android</a>
              <a href={PLAY_STORE_URL} target="_blank" rel="noreferrer">Google Play</a>
              <a href={APP_STORE_URL} target="_blank" rel="noreferrer">App Store</a>
            </div>
          </div>
        </aside>

        <section className="studio-main">
          <PremiumFruitStudio />
        </section>
      </main>
    </>
  );
}
