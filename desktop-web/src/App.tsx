import { FormEvent, useEffect, useState, useRef } from 'react';
import { APP_STORE_URL, ANDROID_APK_URL, APP_VERSION, PLAY_STORE_URL } from './config';
import { fetchDashboardSnapshot, fetchMe, login, type ApiUser } from './api';
import Skeleton from './components/Skeleton';

type Session = {
  token: string;
  user: ApiUser;
};

type DashboardTab = 'feed' | 'market' | 'ai';

function DownloadIcon() {
  return (
    <svg className="buttonIcon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M12 3.25a1 1 0 0 1 1 1v7.34l2.47-2.47a1 1 0 1 1 1.41 1.42l-4.18 4.18a1 1 0 0 1-1.4 0L7.1 10.54a1 1 0 1 1 1.41-1.42L11 11.58V4.25a1 1 0 0 1 1-1ZM5.75 16.5a1 1 0 0 1 1 1v1.25c0 .14.11.25.25.25h10c.14 0 .25-.11.25-.25V17.5a1 1 0 1 1 2 0v1.25A2.25 2.25 0 0 1 17 21H7a2.25 2.25 0 0 1-2.25-2.25V17.5a1 1 0 0 1 1-1Z" />
    </svg>
  );
}

const storageKey = 'wallfruits_session';
const mobileBreakpoint = 900;
const STATUS_LOADING = 'Carregando dados...';
const STATUS_ERROR = 'Nao foi possivel carregar os dados.';
const STATUS_EMPTY = 'Nenhum item encontrado.';

function shouldRedirectToMobileLanding(): boolean {
  if (typeof window === 'undefined') return false;

  const query = new URLSearchParams(window.location.search);
  if (query.get('desktop') === '1') return false;

  if (window.location.pathname === '/mobile-app.html') return false;

  const ua = navigator.userAgent || '';
  const isMobileUa = /android|iphone|ipod|mobile|windows phone|blackberry|opera mini/i.test(ua);
  const isSmallViewport = window.innerWidth <= mobileBreakpoint;
  const isCoarsePointer = window.matchMedia('(pointer: coarse)').matches;

  return isSmallViewport && (isMobileUa || isCoarsePointer);
}

function readSession(): Session | null {
  const raw = localStorage.getItem(storageKey);
  if (!raw) return null;

  try {
    return JSON.parse(raw) as Session;
  } catch {
    return null;
  }
}

export default function App() {
  const [session, setSession] = useState<Session | null>(() => readSession());
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hydrating, setHydrating] = useState(Boolean(session));
  const [offersTotal, setOffersTotal] = useState(0);
  const [ordersTotal, setOrdersTotal] = useState(0);
  const [aiSignals, setAiSignals] = useState(0);
  const [activeTab, setActiveTab] = useState<DashboardTab>('feed');

  useEffect(() => {
    if (!shouldRedirectToMobileLanding()) return;
    window.location.replace('/mobile-app.html');
  }, []);

  // PWA install prompt handling
  useEffect(() => {
    function beforeInstall(e: any) {
      e.preventDefault();
      (window as any).__wfDeferredPrompt = e;
    }
    window.addEventListener('beforeinstallprompt', beforeInstall as EventListener);
    return () => window.removeEventListener('beforeinstallprompt', beforeInstall as EventListener);
  }, []);

  // Swipe gestures for tab switching
  const touchStartX = useRef<number | null>(null);
  function onTouchStart(e: React.TouchEvent) { touchStartX.current = e.touches[0].clientX; }
  function onTouchEnd(e: React.TouchEvent) {
    if (touchStartX.current == null) return;
    const dx = e.changedTouches[0].clientX - touchStartX.current;
    if (Math.abs(dx) < 40) return;
    if (dx < 0) {
      // swipe left -> next tab
      setActiveTab(activeTab === 'feed' ? 'market' : activeTab === 'market' ? 'ai' : 'feed');
    } else {
      // swipe right -> prev tab
      setActiveTab(activeTab === 'ai' ? 'market' : activeTab === 'market' ? 'feed' : 'ai');
    }
    touchStartX.current = null;
  }

  useEffect(() => {
    if (!session?.token) {
      return;
    }

    let mounted = true;
    fetchMe(session.token)
      .then((user) => {
        if (!mounted) return;
        const nextSession = { token: session.token, user };
        setSession(nextSession);
        localStorage.setItem(storageKey, JSON.stringify(nextSession));
      })
      .catch(() => {
        if (!mounted) return;
        localStorage.removeItem(storageKey);
        setSession(null);
      })
      .finally(() => {
        if (mounted) setHydrating(false);
      });

    return () => {
      mounted = false;
    };
  }, [session?.token]);

  useEffect(() => {
    if (!session?.token) {
      return;
    }

    let mounted = true;
    fetchDashboardSnapshot(session.token)
      .then((snapshot) => {
        if (!mounted) return;
        setOffersTotal(snapshot.offersTotal);
        setOrdersTotal(snapshot.ordersTotal);
        setAiSignals(snapshot.aiSignals);
      })
      .catch(() => {
        if (!mounted) return;
        setOffersTotal(0);
        setOrdersTotal(0);
        setAiSignals(0);
      });

    return () => {
      mounted = false;
    };
  }, [session?.token]);

  const sidebar = (
    <aside className="sidebar">
      <div>
        <div className="eyebrow">WallFruits Desktop</div>
        <h2 className="sidebarTitle">Central oficial do software</h2>
        <p>
          Baixe o APK Android oficial, acompanhe a versão do desktop e use os atalhos de distribuição do produto.
        </p>
      </div>

      <div className="sidebarActions">
        <a className="button sidebarButton" href={ANDROID_APK_URL}>
          <DownloadIcon />
          Baixar APK Android oficial
        </a>
        <a className="button buttonSecondary sidebarButton" href={PLAY_STORE_URL} target="_blank" rel="noreferrer">
          Google Play
        </a>
        <a className="button buttonSecondary sidebarButton" href={APP_STORE_URL} target="_blank" rel="noreferrer">
          App Store
        </a>
      </div>

      <div className="versionPanel">
        <span>Versão do software</span>
        <strong>v{APP_VERSION}</strong>
        <p>A versão exibida aqui acompanha o build publicado do desktop web.</p>
      </div>
    </aside>
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const response = await login(email, password);
      const nextSession = { token: response.access_token, user: response.user };
      setSession(nextSession);
      localStorage.setItem(storageKey, JSON.stringify(nextSession));
    } catch (err) {
      setError(err instanceof Error ? err.message : STATUS_ERROR);
    } finally {
      setLoading(false);
    }
  }

  function logout() {
    localStorage.removeItem(storageKey);
    setSession(null);
    setEmail('');
    setPassword('');
    setOffersTotal(0);
    setOrdersTotal(0);
    setAiSignals(0);
    setActiveTab('feed');
  }

  function promptInstall() {
    const deferred = (window as any).__wfDeferredPrompt;
    if (!deferred) return;
    deferred.prompt();
    deferred.userChoice.then(() => {
      (window as any).__wfDeferredPrompt = null;
    });
  }

  async function refreshDashboard() {
    if (!session?.token) return;
    try {
      const snapshot = await fetchDashboardSnapshot(session.token);
      setOffersTotal(snapshot.offersTotal);
      setOrdersTotal(snapshot.ordersTotal);
      setAiSignals(snapshot.aiSignals);
    } catch {
      setError(STATUS_ERROR);
    }
  }

  if (hydrating) {
    return (
      <>
        <header className="topbar">
          <div className="topbarBrand">
            <span className="topbarDot" />
            <span>WallFruits Desktop</span>
          </div>
          <div className="topbarCenter">
            <span className="topbarBadge">Home web</span>
            <span className="topbarText">Scroll principal com experiência premium</span>
          </div>
          <div className="topbarRight">v{APP_VERSION} <button className="button buttonSmall" onClick={promptInstall} style={{marginLeft:8}}>Instalar</button></div>
        </header>
        <main className="shell">
          {sidebar}
          <section className="content">
            <section className="hero">
              <div className="eyebrow">WallFruits Desktop</div>
              <h1>{STATUS_LOADING}</h1>
              <Skeleton lines={4} />
            </section>
          </section>
        </main>
      </>
    );
  }

  if (session) {
    return (
      <>
        <header className="topbar">
          <div className="topbarBrand">
            <span className="topbarDot" />
            <span>WallFruits Desktop</span>
          </div>
          <div className="topbarCenter">
            <span className="topbarBadge">Sessao ativa</span>
            <span className="topbarText">{session.user.name}</span>
          </div>
          <div className="topbarRight">v{APP_VERSION} <button className="button buttonSmall" onClick={promptInstall} style={{marginLeft:8}}>Instalar</button></div>
        </header>
        <main className="shell">
          {sidebar}
          <section className="content">
            <section className="hero feedHero">
              <div className="eyebrow">Inicio</div>
              <h1>WallFruits</h1>
              <p>
                Mesma base visual em iOS, Android e Web: hero, metricas, acoes e cards com a mesma linguagem.
              </p>
              <p className="feedSubline">Sessao ativa: {session.user.name} • {session.user.email}</p>
            </section>

            <section className="tabSwitch" aria-label="Abas principais">
              <button
                type="button"
                className={`tabSwitchBtn ${activeTab === 'feed' ? 'isActive' : ''}`}
                onClick={() => setActiveTab('feed')}
              >
                Feed
              </button>
              <button
                type="button"
                className={`tabSwitchBtn ${activeTab === 'market' ? 'isActive' : ''}`}
                onClick={() => setActiveTab('market')}
              >
                Market
              </button>
              <button
                type="button"
                className={`tabSwitchBtn ${activeTab === 'ai' ? 'isActive' : ''}`}
                onClick={() => setActiveTab('ai')}
              >
                AI
              </button>
            </section>

            <section className="metricsGrid">
              <article className="metricCard">
                <span className="metricLabel">Feed</span>
                <strong>{offersTotal}</strong>
                <p>/api/offers</p>
              </article>
              <article className="metricCard">
                <span className="metricLabel">Marketplace</span>
                <strong>{ordersTotal}</strong>
                <p>/api/store/orders/my</p>
              </article>
              <article className="metricCard">
                <span className="metricLabel">AI</span>
                <strong>{aiSignals}</strong>
                <p>/api/ai/agenda/market-intelligence</p>
              </article>
              <article className="metricCard">
                <span className="metricLabel">Sessao</span>
                <strong>1</strong>
                <p>JWT ativo</p>
              </article>
            </section>

            <section className="actionRow">
              <button className="button" onClick={refreshDashboard} type="button">
                Atualizar
              </button>
              <button className="button buttonSecondary" onClick={logout} type="button">
                Sair
              </button>
            </section>

            <section className="feedStack">
              <div onTouchStart={onTouchStart} onTouchEnd={onTouchEnd}>
              <article className="feedCard feedCardPrimary">
                <h2>Sessao</h2>
                <p>JWT ativo para {session.user.name}</p>
              </article>
              {offersTotal === 0 && ordersTotal === 0 && aiSignals === 0 ? (
                <article className="feedCard">
                  <h2>Vazio</h2>
                  <p>{STATUS_EMPTY}</p>
                </article>
              ) : null}
              <article className="feedCard">
                <h2>Feed</h2>
                <p>/api/offers: {offersTotal}</p>
              </article>
              <article className="feedCard">
                <h2>Marketplace</h2>
                <p>/api/store/orders/my: {ordersTotal}</p>
              </article>
              <article className="feedCard">
                <h2>AI</h2>
                <p>/api/ai/agenda/market-intelligence: {aiSignals}</p>
              </article>
              </div>
            </section>
          </section>
        </main>
      </>
    );
  }

  return (
    <>
      <header className="topbar">
        <div className="topbarBrand">
          <span className="topbarDot" />
          <span>WallFruits Desktop</span>
        </div>
        <div className="topbarCenter">
          <span className="topbarBadge">Entrar</span>
          <span className="topbarText">Acesso ao desktop com login persistente</span>
        </div>
        <div className="topbarRight">v{APP_VERSION} <button className="button buttonSmall" onClick={promptInstall} style={{marginLeft:8}}>Instalar</button></div>
      </header>
      <main className="shell">
        {sidebar}
        <section className="content">
          <section className="hero">
            <div className="eyebrow">Central de acesso</div>
            <h1>Bem-vindo</h1>

            <form className="loginForm" onSubmit={handleSubmit}>
              <input
                className="input"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="Email"
                autoComplete="email"
                type="email"
                required
              />
              <input
                className="input"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Senha"
                autoComplete="current-password"
                type="password"
                required
              />
              {error ? <p className="error">{error}</p> : null}
              <button className="button" type="submit" disabled={loading}>
                {loading ? 'Entrando...' : 'Entrar'}
              </button>
            </form>
          </section>

          <section className="grid">
            <article className="card">
              <h2>Mobile nativo</h2>
              <p>Android e iOS continuam priorizados como app principal.</p>
            </article>
            <article className="card">
              <h2>Desktop apenas</h2>
              <p>No celular, a web redireciona para a pagina do app nativo.</p>
            </article>
            <article className="card">
              <h2>Lojas</h2>
              <p>
                <a href={PLAY_STORE_URL}>Google Play</a> e <a href={APP_STORE_URL}>App Store</a>
              </p>
            </article>
          </section>
        </section>
      </main>
    </>
  );
}
