import { FormEvent, useEffect, useMemo, useState } from 'react';
import { APP_STORE_URL, PLAY_STORE_URL } from './config';
import { fetchMe, login, type ApiUser } from './api';

type Session = {
  token: string;
  user: ApiUser;
};

const storageKey = 'wallfruits_session';

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

  const stack = useMemo(() => ['React', 'TypeScript', 'JWT', 'FastAPI', 'Vite'], []);

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
      setError(err instanceof Error ? err.message : 'Falha ao autenticar');
    } finally {
      setLoading(false);
    }
  }

  function logout() {
    localStorage.removeItem(storageKey);
    setSession(null);
    setEmail('');
    setPassword('');
  }

  if (hydrating) {
    return (
      <main className="page">
        <section className="hero">
          <div className="eyebrow">WallFruits Desktop</div>
          <h1>Carregando sua sessao...</h1>
        </section>
      </main>
    );
  }

  if (session) {
    return (
      <main className="page">
        <section className="hero">
          <div className="eyebrow">Sessao ativa</div>
          <h1>Bem-vindo, {session.user.name}</h1>
          <p>{session.user.email}</p>
          <div className="chips">
            {stack.map((item) => (
              <span className="chip" key={item}>
                {item}
              </span>
            ))}
          </div>
          <div style={{ marginTop: 20 }}>
            <button className="button" onClick={logout} type="button">
              Sair
            </button>
          </div>
        </section>

        <section className="grid">
          <article className="card">
            <h2>Feed</h2>
            <p>Autenticacao JWT integrada com o backend real.</p>
          </article>
          <article className="card">
            <h2>Marketplace</h2>
            <p>Estrutura pronta para conectores de ofertas e compras.</p>
          </article>
          <article className="card">
            <h2>AI Lab</h2>
            <p>Base para automacao e assistentes no desktop.</p>
          </article>
        </section>
      </main>
    );
  }

  return (
    <main className="page">
      <section className="hero">
        <div className="eyebrow">WallFruits Desktop</div>
        <h1>Entrar com JWT no desktop web.</h1>
        <p>Use o mesmo login da API para acessar o desktop com sessao persistente.</p>

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

        <div className="chips">
          {stack.map((item) => (
            <span className="chip" key={item}>
              {item}
            </span>
          ))}
        </div>
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
    </main>
  );
}
