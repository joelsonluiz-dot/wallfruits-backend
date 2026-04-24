const features = [
  {
    title: 'Feed visual',
    description: 'Desenvolvido para descoberta, interacao e consumo rapido de conteudo.',
  },
  {
    title: 'Marketplace',
    description: 'Camada comercial integrada ao ecossistema principal.',
  },
  {
    title: 'AI Lab',
    description: 'Ferramentas de automacao e assistencia inteligente.',
  },
];

const stack = ['React', 'TypeScript', 'Vite', 'Nginx', 'FastAPI'];

export default function App() {
  return (
    <main className="page">
      <section className="hero">
        <div className="eyebrow">WallFruits Desktop</div>
        <h1>Web desktop no padrao de um produto social moderno.</h1>
        <p>
          Esta e a camada web oficial para desktop, alinhada ao novo modelo do produto: mobile nativo e
          web restrita ao computador.
        </p>

        <div className="chips">
          {stack.map((item) => (
            <span className="chip" key={item}>
              {item}
            </span>
          ))}
        </div>
      </section>

      <section className="grid">
        {features.map((feature) => (
          <article className="card" key={feature.title}>
            <h2>{feature.title}</h2>
            <p>{feature.description}</p>
          </article>
        ))}
      </section>
    </main>
  );
}
