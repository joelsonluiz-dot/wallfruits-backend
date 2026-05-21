import { useEffect, useMemo, useRef, useState, type DragEvent, type ReactNode } from 'react';
import './premium-fruit-studio.css';

type MoneyField = 'minPrice' | 'avgPrice' | 'maxPrice' | 'pricePerKg' | 'pricePerBox';
type StepKey = 'image' | 'pricing' | 'product' | 'certifications' | 'logistics' | 'dates' | 'property' | 'quantity' | 'final';

type FormState = {
  fruitName: string;
  variety: string;
  quality: string;
  origin: string;
  market: string;
  maturity: string;
  farmName: string;
  farmAddress: string;
  description: string;
  harvestDate: string;
  reserveStart: string;
  reserveEnd: string;
  validityDate: string;
  minPrice: string;
  avgPrice: string;
  maxPrice: string;
  pricePerKg: string;
  pricePerBox: string;
  weightBox: string;
  availableQuantity: string;
  minBoxes: number;
  minFruitUnits: number;
};

const STEP_DEFINITIONS: Array<{ key: StepKey; label: string; helper: string }> = [
  { key: 'image', label: 'Imagem', helper: 'Upload, câmera e preview' },
  { key: 'pricing', label: 'Preços', helper: 'Máscara monetária inteligente' },
  { key: 'product', label: 'Produto', helper: 'Nome, variedade e qualidade' },
  { key: 'certifications', label: 'Certificações', helper: 'Multi select premium' },
  { key: 'logistics', label: 'Logística', helper: 'Origem, mercado e maturação' },
  { key: 'dates', label: 'Datas', helper: 'Colheita e reservas' },
  { key: 'property', label: 'Propriedade', helper: 'Contexto e descrição' },
  { key: 'quantity', label: 'Quantidade', helper: 'Controle de estoque' },
  { key: 'final', label: 'Finalização', helper: 'Revisão e publicação' },
];

const CERTIFICATIONS = ['Global GAP', 'Orgânico', 'Fair Trade', 'Bonsucro', 'RainForest Alliance', 'UTZ Certified', 'ISO 14001'];
const FRUIT_LIBRARY = [
  { name: 'Manga', varieties: ['Palmer', 'Tommy', 'Kent', 'Haden'], qualities: ['Premium', 'Seleção A', 'Exportação'] },
  { name: 'Banana', varieties: ['Prata', 'Nanica', 'Maçã', 'Ouro'], qualities: ['Prime', 'Mercado interno', 'Madura'] },
  { name: 'Uva', varieties: ['Thompson', 'BRS Vitória', 'Crimson', 'Italia'], qualities: ['Premium', 'Sem semente', 'Mesa'] },
  { name: 'Maçã', varieties: ['Gala', 'Fuji', 'Pink Lady', 'Sundowner'], qualities: ['Classe 1', 'Top export', 'Selecionada'] },
  { name: 'Laranja', varieties: ['Pera', 'Valencia', 'Lima', 'Bahia'], qualities: ['Suco', 'Mesa', 'Brix alto'] },
];
const ORIGINS = ['São Paulo', 'Minas Gerais', 'Bahia', 'Pernambuco', 'Goiás', 'Paraná'];
const MARKETS = ['Hortifruti premium', 'Atacado', 'Supermercado', 'Exportação', 'Restaurantes'];
const MATURITIES = ['Verde', 'Ponto de colheita', 'Madura', 'Pronta para despacho'];

const initialState: FormState = {
  fruitName: 'Manga',
  variety: 'Palmer',
  quality: 'Premium',
  origin: 'Bahia',
  market: 'Exportação',
  maturity: 'Ponto de colheita',
  farmName: '',
  farmAddress: '',
  description: '',
  harvestDate: '',
  reserveStart: '',
  reserveEnd: '',
  validityDate: '',
  minPrice: 'R$ 18,00',
  avgPrice: 'R$ 22,00',
  maxPrice: 'R$ 29,00',
  pricePerKg: 'R$ 4,20',
  pricePerBox: 'R$ 42,00',
  weightBox: '18',
  availableQuantity: '420',
  minBoxes: 12,
  minFruitUnits: 48,
};

type ValidationState = Record<string, string>;

function formatCurrency(value: string): string {
  const digits = value.replace(/\D/g, '');
  if (!digits) return '';
  const numberValue = Number(digits) / 100;
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(numberValue);
}

function currencyToNumber(value: string): number {
  const normalized = value.replace(/[^\d,.-]/g, '').replace(/\./g, '').replace(',', '.');
  return Number(normalized) || 0;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getFruitOptions(name: string): string[] {
  return FRUIT_LIBRARY.find((fruit) => fruit.name === name)?.varieties ?? FRUIT_LIBRARY[0].varieties;
}

function getQualityOptions(name: string): string[] {
  return FRUIT_LIBRARY.find((fruit) => fruit.name === name)?.qualities ?? FRUIT_LIBRARY[0].qualities;
}

function createConfetti() {
  return Array.from({ length: 24 }).map((_, index) => ({
    id: index,
    left: `${Math.random() * 100}%`,
    delay: `${Math.random() * 0.45}s`,
    hue: [230, 258, 190, 320, 200][index % 5],
  }));
}

async function compressImage(file: File): Promise<{ previewUrl: string; optimizedSize: string }> {
  if (typeof window === 'undefined') {
    return { previewUrl: '', optimizedSize: formatBytes(file.size) };
  }

  const objectUrl = URL.createObjectURL(file);
  if (!('createImageBitmap' in window)) {
    return { previewUrl: objectUrl, optimizedSize: formatBytes(file.size) };
  }

  try {
    const bitmap = await createImageBitmap(file);
    const maxSide = 1800;
    const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(1, Math.round(bitmap.width * scale));
    canvas.height = Math.max(1, Math.round(bitmap.height * scale));
    const context = canvas.getContext('2d');
    if (!context) {
      return { previewUrl: objectUrl, optimizedSize: formatBytes(file.size) };
    }

    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    const optimizedBlob = await new Promise<Blob>((resolve) => {
      canvas.toBlob((blob) => resolve(blob ?? file), 'image/jpeg', 0.82);
    });

    return {
      previewUrl: URL.createObjectURL(optimizedBlob),
      optimizedSize: formatBytes(optimizedBlob.size),
    };
  } catch {
    return { previewUrl: objectUrl, optimizedSize: formatBytes(file.size) };
  }
}

function validate(values: FormState, certifications: string[], imageReady: boolean): ValidationState {
  const nextErrors: ValidationState = {};

  if (!imageReady) nextErrors.image = 'Adicione a imagem principal da fruta.';
  if (!values.fruitName.trim()) nextErrors.fruitName = 'Informe o nome da fruta.';
  if (!values.variety.trim()) nextErrors.variety = 'Selecione a variedade.';
  if (!values.quality.trim()) nextErrors.quality = 'Selecione a qualidade.';
  if (!certifications.length) nextErrors.certifications = 'Escolha ao menos uma certificação.';
  if (!values.origin.trim()) nextErrors.origin = 'Informe a origem.';
  if (!values.market.trim()) nextErrors.market = 'Informe o mercado de venda.';
  if (!values.maturity.trim()) nextErrors.maturity = 'Informe o grau de maturação.';
  if (!values.farmName.trim()) nextErrors.farmName = 'Informe o nome da propriedade.';
  if (!values.farmAddress.trim()) nextErrors.farmAddress = 'Informe o endereço da propriedade.';
  if (!values.description.trim()) nextErrors.description = 'Descreva o produto.';
  if (!values.harvestDate) nextErrors.harvestDate = 'Escolha a data da colheita.';
  if (!values.reserveStart) nextErrors.reserveStart = 'Escolha o início da reserva.';
  if (!values.reserveEnd) nextErrors.reserveEnd = 'Escolha o fim da reserva.';
  if (!values.validityDate) nextErrors.validityDate = 'Escolha a validade.';

  const min = currencyToNumber(values.minPrice);
  const avg = currencyToNumber(values.avgPrice);
  const max = currencyToNumber(values.maxPrice);
  const perKg = currencyToNumber(values.pricePerKg);
  const perBox = currencyToNumber(values.pricePerBox);

  if (min <= 0) nextErrors.minPrice = 'Defina o preço mínimo.';
  if (avg <= 0) nextErrors.avgPrice = 'Defina o preço médio.';
  if (max <= 0) nextErrors.maxPrice = 'Defina o preço máximo.';
  if (perKg <= 0) nextErrors.pricePerKg = 'Defina o preço por kg.';
  if (perBox <= 0) nextErrors.pricePerBox = 'Defina o preço por caixa.';
  if (min && avg && max && !(min <= avg && avg <= max)) nextErrors.maxPrice = 'Mantenha a progressão mínima, média e máxima.';

  if (!values.weightBox.trim()) nextErrors.weightBox = 'Informe o peso da caixa.';
  if (!values.availableQuantity.trim()) nextErrors.availableQuantity = 'Informe a quantidade disponível.';
  if (values.minBoxes < 1) nextErrors.minBoxes = 'A quantidade mínima de caixas precisa ser maior que zero.';
  if (values.minFruitUnits < 1) nextErrors.minFruitUnits = 'A quantidade mínima da fruta precisa ser maior que zero.';

  return nextErrors;
}

function FieldShell({
  label,
  hint,
  error,
  success,
  loading,
  children,
}: {
  label: string;
  hint?: string;
  error?: string;
  success?: string;
  loading?: boolean;
  children: ReactNode;
}) {
  return (
    <label className="studio-field" data-loading={loading ? 'true' : 'false'}>
      <span className="studio-fieldLabel">{label}</span>
      <div className="studio-fieldControl">{children}</div>
      <div className="studio-fieldMeta">
        <span>{error ?? success ?? hint}</span>
      </div>
    </label>
  );
}

function PremiumCombobox({
  label,
  value,
  onChange,
  options,
  placeholder,
  hint,
  error,
  success,
}: {
  label: string;
  value: string;
  onChange: (nextValue: string) => void;
  options: string[];
  placeholder: string;
  hint?: string;
  error?: string;
  success?: string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState(value);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setQuery(value);
  }, [value]);

  useEffect(() => {
    function handleOutside(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false);
    }

    window.addEventListener('mousedown', handleOutside);
    window.addEventListener('keydown', handleEscape);
    return () => {
      window.removeEventListener('mousedown', handleOutside);
      window.removeEventListener('keydown', handleEscape);
    };
  }, []);

  const filtered = options.filter((option) => option.toLowerCase().includes(query.toLowerCase()));

  return (
    <label className="studio-field" ref={containerRef}>
      <span className="studio-fieldLabel">{label}</span>
      <div className="studio-comboboxWrap">
        <input
          className="studio-input"
          value={query}
          placeholder={placeholder}
          onChange={(event) => {
            const nextValue = event.target.value;
            setQuery(nextValue);
            onChange(nextValue);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
        />
        {open ? (
          <div className="studio-popover">
            {filtered.length ? (
              filtered.slice(0, 6).map((option) => (
                <button
                  key={option}
                  type="button"
                  className={`studio-suggestion ${option === value ? 'isActive' : ''}`}
                  onClick={() => {
                    onChange(option);
                    setQuery(option);
                    setOpen(false);
                  }}
                >
                  {option}
                </button>
              ))
            ) : (
              <div className="studio-emptySuggestion">Nenhuma opção encontrada.</div>
            )}
          </div>
        ) : null}
      </div>
      <div className="studio-fieldMeta">
        <span>{error ?? success ?? hint}</span>
      </div>
    </label>
  );
}

function PremiumMultiSelect({
  label,
  values,
  onChange,
  options,
  hint,
  error,
}: {
  label: string;
  values: string[];
  onChange: (nextValues: string[]) => void;
  options: string[];
  hint?: string;
  error?: string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    function onClose(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }

    window.addEventListener('mousedown', onClose);
    return () => window.removeEventListener('mousedown', onClose);
  }, []);

  const filtered = options.filter((option) => option.toLowerCase().includes(query.toLowerCase()));

  function toggleOption(option: string) {
    const nextValues = values.includes(option) ? values.filter((item) => item !== option) : [...values, option];
    onChange(nextValues);
  }

  return (
    <div className="studio-field" ref={rootRef}>
      <span className="studio-fieldLabel">{label}</span>
      <button type="button" className="studio-chipInput" onClick={() => setOpen((current) => !current)}>
        <span className="studio-chipInputLabel">{values.length ? `${values.length} selecionadas` : 'Selecionar certificações'}</span>
        <span className="studio-chipInputCaret">▾</span>
      </button>
      <div className="studio-chipStack">
        {values.map((value) => (
          <button key={value} type="button" className="studio-selectedChip" onClick={() => toggleOption(value)}>
            {value}
            <span aria-hidden="true">×</span>
          </button>
        ))}
      </div>
      {open ? (
        <div className="studio-popover studio-popoverLarge">
          <input
            className="studio-input studio-inputGhost"
            placeholder="Buscar certificação..."
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <div className="studio-optionList">
            {filtered.map((option) => {
              const active = values.includes(option);
              return (
                <button
                  key={option}
                  type="button"
                  className={`studio-suggestion studio-suggestionCheckbox ${active ? 'isActive' : ''}`}
                  onClick={() => toggleOption(option)}
                >
                  <span>{option}</span>
                  <span>{active ? 'Selecionado' : 'Adicionar'}</span>
                </button>
              );
            })}
          </div>
        </div>
      ) : null}
      <div className="studio-fieldMeta">
        <span>{error ?? hint}</span>
      </div>
    </div>
  );
}

function PremiumCounter({
  label,
  value,
  onChange,
  hint,
  error,
}: {
  label: string;
  value: number;
  onChange: (updater: (currentValue: number) => number) => void;
  hint?: string;
  error?: string;
}) {
  const timerRef = useRef<number | null>(null);

  useEffect(() => () => {
    if (timerRef.current) window.clearInterval(timerRef.current);
  }, []);

  function startHold(step: number) {
    onChange((currentValue) => Math.max(0, currentValue + step));
    timerRef.current = window.setInterval(() => {
      onChange((currentValue) => Math.max(0, currentValue + step));
    }, 120);
  }

  function stopHold() {
    if (timerRef.current) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }

  return (
    <div className="studio-field">
      <span className="studio-fieldLabel">{label}</span>
      <div className="studio-counter">
        <button type="button" className="studio-counterButton" onPointerDown={() => startHold(-1)} onPointerUp={stopHold} onPointerLeave={stopHold} onPointerCancel={stopHold}>−</button>
        <div className="studio-counterValue">{value}</div>
        <button type="button" className="studio-counterButton" onPointerDown={() => startHold(1)} onPointerUp={stopHold} onPointerLeave={stopHold} onPointerCancel={stopHold}>+</button>
      </div>
      <div className="studio-fieldMeta">
        <span>{error ?? hint}</span>
      </div>
    </div>
  );
}

export default function PremiumFruitStudio() {
  const [stepIndex, setStepIndex] = useState(0);
  const [values, setValues] = useState<FormState>(initialState);
  const [certifications, setCertifications] = useState<string[]>(['Global GAP', 'Orgânico']);
  const [imagePreview, setImagePreview] = useState('');
  const [imageName, setImageName] = useState('Imagem principal ainda não enviada');
  const [imageSize, setImageSize] = useState('0 B');
  const [imageLoading, setImageLoading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [errors, setErrors] = useState<ValidationState>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [publishState, setPublishState] = useState<'idle' | 'loading' | 'success'>('idle');
  const [confetti, setConfetti] = useState<Array<{ id: number; left: string; delay: string; hue: number }>>([]);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const previewUrlRef = useRef<string | null>(null);

  const step = STEP_DEFINITIONS[stepIndex];
  const availableVarieties = useMemo(() => getFruitOptions(values.fruitName), [values.fruitName]);
  const availableQualities = useMemo(() => getQualityOptions(values.fruitName), [values.fruitName]);
  const completion = Math.round(((stepIndex + 1) / STEP_DEFINITIONS.length) * 100);
  const summaryPriceSpread = useMemo(() => {
    const min = currencyToNumber(values.minPrice);
    const max = currencyToNumber(values.maxPrice);
    if (!min || !max) return 'Defina a faixa de preço.';
    const spread = max - min;
    return spread > 0 ? `Amplitude de ${new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(spread)}.` : 'Faixa coerente e estável.';
  }, [values.maxPrice, values.minPrice]);

  useEffect(() => {
    const nextErrors = validate(values, certifications, Boolean(imagePreview));
    setErrors(nextErrors);
  }, [certifications, imagePreview, values]);

  useEffect(() => {
    return () => {
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    };
  }, []);

  useEffect(() => {
    if (!availableVarieties.includes(values.variety)) {
      setValues((currentValue) => ({ ...currentValue, variety: availableVarieties[0] }));
    }
    if (!availableQualities.includes(values.quality)) {
      setValues((currentValue) => ({ ...currentValue, quality: availableQualities[0] }));
    }
  }, [availableQualities, availableVarieties, values.quality, values.variety]);

  function vibrate(pattern: number | number[]) {
    if (typeof navigator !== 'undefined' && 'vibrate' in navigator) navigator.vibrate(pattern);
  }

  function markTouched(field: string) {
    setTouched((currentValue) => ({ ...currentValue, [field]: true }));
  }

  function updateField(field: keyof FormState, nextValue: string | number) {
    setValues((currentValue) => ({ ...currentValue, [field]: nextValue }));
  }

  function updateMoneyField(field: MoneyField, nextValue: string) {
    updateField(field, formatCurrency(nextValue));
  }

  async function handleFile(file: File | null) {
    if (!file) return;
    setImageLoading(true);
    const nextPreview = await compressImage(file);
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    previewUrlRef.current = nextPreview.previewUrl;
    setImagePreview(nextPreview.previewUrl);
    setImageName(file.name);
    setImageSize(nextPreview.optimizedSize);
    setImageLoading(false);
    markTouched('image');
    vibrate(12);
  }

  function openFilePicker() {
    fileInputRef.current?.click();
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragActive(false);
    void handleFile(event.dataTransfer.files[0] ?? null);
  }

  function goNext() {
    setStepIndex((currentValue) => Math.min(STEP_DEFINITIONS.length - 1, currentValue + 1));
    vibrate(10);
  }

  function goBack() {
    setStepIndex((currentValue) => Math.max(0, currentValue - 1));
    vibrate(8);
  }

  async function handlePublish() {
    const nextErrors = validate(values, certifications, Boolean(imagePreview));
    setTouched(
      Object.keys(nextErrors).reduce<Record<string, boolean>>((accumulator, key) => {
        accumulator[key] = true;
        return accumulator;
      }, {}),
    );
    setErrors(nextErrors);

    if (Object.keys(nextErrors).length) {
      vibrate([18, 18, 32]);
      return;
    }

    setPublishState('loading');
    vibrate(14);
    await new Promise((resolve) => window.setTimeout(resolve, 1400));
    setPublishState('success');
    setConfetti(createConfetti());
    vibrate([12, 24, 12]);
    window.setTimeout(() => setPublishState('idle'), 2600);
    window.setTimeout(() => setConfetti([]), 2600);
  }

  const commonMoneyError = (field: MoneyField) => (touched[field] ? errors[field] : '');
  const commonError = (field: keyof FormState | string) => (touched[field] ? errors[field] : '');

  return (
    <section className="studio-page">
      <div className="studio-glow studio-glowA" />
      <div className="studio-glow studio-glowB" />
      <div className="studio-layout">
        <article className="studio-formShell">
          <header className="studio-formHero">
            <div className="studio-heroPill">Interface premium • iOS • Android • Web</div>
            <h2>Cadastro de produto agrícola ultra premium</h2>
            <p>Preenchimento em etapas, validação instantânea, estados refinados e experiência de luxo em qualquer tela.</p>
            <div className="studio-progressBar" aria-label="Progresso do cadastro">
              <span style={{ width: `${completion}%` }} />
            </div>
            <div className="studio-stepper" aria-label="Etapas do formulário">
              {STEP_DEFINITIONS.map((item, index) => (
                <button
                  key={item.key}
                  type="button"
                  className={`studio-stepChip ${index === stepIndex ? 'isActive' : ''}`}
                  onClick={() => {
                    setStepIndex(index);
                    vibrate(6);
                  }}
                >
                  <strong>{index + 1}</strong>
                  <span>
                    {item.label}
                    <small>{item.helper}</small>
                  </span>
                </button>
              ))}
            </div>
          </header>

          <div className="studio-sectionGrid">
            <section className={`studio-section ${step.key === 'image' ? 'isVisible' : ''}`}>
              <div className="studio-sectionHeader">
                <div>
                  <h3>Upload de imagem</h3>
                  <p>Drag-and-drop, câmera, preview cinematográfico e compressão automática.</p>
                </div>
                <span className="studio-sectionBadge">01</span>
              </div>
              <div
                className={`studio-dropzone ${dragActive ? 'isActive' : ''} ${imageLoading ? 'isLoading' : ''}`}
                onDragOver={(event) => {
                  event.preventDefault();
                  setDragActive(true);
                }}
                onDragLeave={() => setDragActive(false)}
                onDrop={handleDrop}
                onClick={openFilePicker}
                role="button"
                tabIndex={0}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') openFilePicker();
                }}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  capture="environment"
                  className="studio-hiddenInput"
                  onChange={(event) => void handleFile(event.target.files?.[0] ?? null)}
                />
                {imageLoading ? (
                  <div className="studio-skeleton">
                    <div />
                    <div />
                    <div />
                  </div>
                ) : imagePreview ? (
                  <div className="studio-preview">
                    <img src={imagePreview} alt="Preview da fruta" />
                    <div className="studio-previewMeta">
                      <strong>{imageName}</strong>
                      <span>Imagem otimizada · {imageSize}</span>
                    </div>
                  </div>
                ) : (
                  <div className="studio-dropzoneContent">
                    <div className="studio-dropIcon">✦</div>
                    <h4>Solte a imagem principal aqui</h4>
                    <p>Toque para abrir a câmera ou escolher do dispositivo.</p>
                    <div className="studio-inlineActions">
                      <button type="button" className="studio-button studio-buttonGhost" onClick={openFilePicker}>
                        Selecionar imagem
                      </button>
                      <button type="button" className="studio-button studio-buttonSecondary" onClick={openFilePicker}>
                        Abrir câmera
                      </button>
                    </div>
                  </div>
                )}
              </div>
              <div className="studio-fieldMeta studio-fieldMetaWide">
                <span>{commonError('image') || 'Aceita imagens modernas com ajuste automático de peso e resolução.'}</span>
              </div>
            </section>

            <section className={`studio-section ${step.key === 'pricing' ? 'isVisible' : ''}`}>
              <div className="studio-sectionHeader">
                <div>
                  <h3>Preços</h3>
                  <p>Mascara monetária inteligente com feedback instantâneo.</p>
                </div>
                <span className="studio-sectionBadge">02</span>
              </div>
              <div className="studio-gridTwo">
                {([
                  ['Preço mínimo', 'minPrice'],
                  ['Preço médio', 'avgPrice'],
                  ['Preço máximo', 'maxPrice'],
                  ['Preço por kg', 'pricePerKg'],
                  ['Preço por caixa', 'pricePerBox'],
                ] as Array<[string, MoneyField]>).map(([label, field]) => (
                  <FieldShell key={field} label={label} error={commonMoneyError(field)} success={touched[field] && !errors[field] ? 'OK' : ''}>
                    <input
                      className="studio-input"
                      value={values[field]}
                      inputMode="decimal"
                      placeholder="R$ 0,00"
                      onChange={(event) => updateMoneyField(field, event.target.value)}
                      onBlur={() => markTouched(field)}
                    />
                  </FieldShell>
                ))}
              </div>
              <div className="studio-chipRow studio-chipRowCompact">
                <span className="studio-statusChip">{summaryPriceSpread}</span>
                <span className="studio-statusChip">Highlight automático em foco</span>
              </div>
            </section>

            <section className={`studio-section ${step.key === 'product' ? 'isVisible' : ''}`}>
              <div className="studio-sectionHeader">
                <div>
                  <h3>Produto</h3>
                  <p>Combobox premium com sugestões inteligentes e chips animados.</p>
                </div>
                <span className="studio-sectionBadge">03</span>
              </div>
              <div className="studio-gridTwo">
                <PremiumCombobox label="Nome da fruta" value={values.fruitName} onChange={(nextValue) => updateField('fruitName', nextValue)} options={FRUIT_LIBRARY.map((fruit) => fruit.name)} placeholder="Buscar fruta" hint="Autocomplete premium" error={commonError('fruitName')} success={touched.fruitName && !errors.fruitName ? 'Sugestão encontrada' : ''} />
                <PremiumCombobox label="Variedade" value={values.variety} onChange={(nextValue) => updateField('variety', nextValue)} options={availableVarieties} placeholder="Buscar variedade" hint="Busca instantânea" error={commonError('variety')} success={touched.variety && !errors.variety ? 'Selecionada' : ''} />
                <PremiumCombobox label="Qualidade" value={values.quality} onChange={(nextValue) => updateField('quality', nextValue)} options={availableQualities} placeholder="Buscar qualidade" hint="Classificação refinada" error={commonError('quality')} success={touched.quality && !errors.quality ? 'Selecionada' : ''} />
                <div className="studio-field">
                  <span className="studio-fieldLabel">Visual rápido</span>
                  <div className="studio-chipStack studio-chipStackInline">
                    <span className="studio-selectedChip">{values.fruitName}</span>
                    <span className="studio-selectedChip">{values.variety}</span>
                    <span className="studio-selectedChip">{values.quality}</span>
                  </div>
                </div>
              </div>
            </section>

            <section className={`studio-section ${step.key === 'certifications' ? 'isVisible' : ''}`}>
              <div className="studio-sectionHeader">
                <div>
                  <h3>Certificações</h3>
                  <p>Seleção multilayer com popup blur moderno.</p>
                </div>
                <span className="studio-sectionBadge">04</span>
              </div>
              <PremiumMultiSelect label="Certificações do produto" values={certifications} onChange={setCertifications} options={CERTIFICATIONS} hint="Multi select premium e chips refinados" error={commonError('certifications')} />
            </section>

            <section className={`studio-section ${step.key === 'logistics' ? 'isVisible' : ''}`}>
              <div className="studio-sectionHeader">
                <div>
                  <h3>Logística</h3>
                  <p>Origem, mercado, maturação e validade com UX de alto nível.</p>
                </div>
                <span className="studio-sectionBadge">05</span>
              </div>
              <div className="studio-gridTwo">
                <PremiumCombobox label="Origem" value={values.origin} onChange={(nextValue) => updateField('origin', nextValue)} options={ORIGINS} placeholder="Buscar origem" error={commonError('origin')} />
                <PremiumCombobox label="Mercado de venda" value={values.market} onChange={(nextValue) => updateField('market', nextValue)} options={MARKETS} placeholder="Buscar mercado" error={commonError('market')} />
                <PremiumCombobox label="Grau de maturação" value={values.maturity} onChange={(nextValue) => updateField('maturity', nextValue)} options={MATURITIES} placeholder="Buscar maturação" error={commonError('maturity')} />
                <FieldShell label="Peso da caixa" hint="Kg por caixa">
                  <input className="studio-input" value={values.weightBox} inputMode="decimal" placeholder="18" onChange={(event) => updateField('weightBox', event.target.value)} />
                </FieldShell>
                <FieldShell label="Quantidade disponível" hint="Unidades em estoque">
                  <input className="studio-input" value={values.availableQuantity} inputMode="numeric" placeholder="420" onChange={(event) => updateField('availableQuantity', event.target.value)} />
                </FieldShell>
                <FieldShell label="Validade" error={commonError('validityDate')}>
                  <input className="studio-input" value={values.validityDate} type="date" onChange={(event) => updateField('validityDate', event.target.value)} onBlur={() => markTouched('validityDate')} />
                </FieldShell>
              </div>
            </section>

            <section className={`studio-section ${step.key === 'dates' ? 'isVisible' : ''}`}>
              <div className="studio-sectionHeader">
                <div>
                  <h3>Datas</h3>
                  <p>Calendário premium com transições suaves e seleção inteligente.</p>
                </div>
                <span className="studio-sectionBadge">06</span>
              </div>
              <div className="studio-gridTwo">
                <FieldShell label="Data da colheita" error={commonError('harvestDate')}>
                  <input className="studio-input" value={values.harvestDate} type="date" onChange={(event) => updateField('harvestDate', event.target.value)} onBlur={() => markTouched('harvestDate')} />
                </FieldShell>
                <FieldShell label="Data inicial reserva" error={commonError('reserveStart')}>
                  <input className="studio-input" value={values.reserveStart} type="date" onChange={(event) => updateField('reserveStart', event.target.value)} onBlur={() => markTouched('reserveStart')} />
                </FieldShell>
                <FieldShell label="Data final reserva" error={commonError('reserveEnd')}>
                  <input className="studio-input" value={values.reserveEnd} type="date" onChange={(event) => updateField('reserveEnd', event.target.value)} onBlur={() => markTouched('reserveEnd')} />
                </FieldShell>
                <div className="studio-rangeCard">
                  <strong>Range intuitivo</strong>
                  <p>Experiência pensada para escolher datas com clareza em desktop e mobile.</p>
                </div>
              </div>
            </section>

            <section className={`studio-section ${step.key === 'property' ? 'isVisible' : ''}`}>
              <div className="studio-sectionHeader">
                <div>
                  <h3>Propriedade</h3>
                  <p>Multiline inteligente com crescimento automático e espaçamento refinado.</p>
                </div>
                <span className="studio-sectionBadge">07</span>
              </div>
              <div className="studio-gridTwo">
                <FieldShell label="Nome da propriedade" error={commonError('farmName')}>
                  <input className="studio-input" value={values.farmName} placeholder="Fazenda Aurora" onChange={(event) => updateField('farmName', event.target.value)} onBlur={() => markTouched('farmName')} />
                </FieldShell>
                <FieldShell label="Endereço da propriedade" error={commonError('farmAddress')}>
                  <input className="studio-input" value={values.farmAddress} placeholder="Rodovia BR-101, km 32" onChange={(event) => updateField('farmAddress', event.target.value)} onBlur={() => markTouched('farmAddress')} />
                </FieldShell>
                <label className="studio-field studio-fieldWide">
                  <span className="studio-fieldLabel">Descrição do produto</span>
                  <textarea className="studio-textarea" value={values.description} placeholder="Descreva o lote, a origem, o ponto de maturação e os diferenciais de qualidade." onChange={(event) => updateField('description', event.target.value)} onBlur={() => markTouched('description')} rows={4} />
                  <div className="studio-fieldMeta"><span>{commonError('description') || 'Auto spacing e crescimento visual premium.'}</span></div>
                </label>
              </div>
            </section>

            <section className={`studio-section ${step.key === 'quantity' ? 'isVisible' : ''}`}>
              <div className="studio-sectionHeader">
                <div>
                  <h3>Quantidade</h3>
                  <p>Contadores com press-and-hold e física suave.</p>
                </div>
                <span className="studio-sectionBadge">08</span>
              </div>
              <div className="studio-gridTwo">
                <PremiumCounter label="Quantidade mínima de caixas" value={values.minBoxes} onChange={(updater) => updateField('minBoxes', updater(values.minBoxes))} hint="Incrementação contínua" error={commonError('minBoxes')} />
                <PremiumCounter label="Quantidade mínima da fruta" value={values.minFruitUnits} onChange={(updater) => updateField('minFruitUnits', updater(values.minFruitUnits))} hint="Gestures e animações físicas" error={commonError('minFruitUnits')} />
              </div>
            </section>

            <section className={`studio-section ${step.key === 'final' ? 'isVisible' : ''}`}>
              <div className="studio-sectionHeader">
                <div>
                  <h3>Finalização</h3>
                  <p>Publicação com loading cinematográfico, sucesso e confetti premium.</p>
                </div>
                <span className="studio-sectionBadge">09</span>
              </div>
              <div className="studio-finalGrid">
                <div className="studio-summaryCard">
                  <span className="studio-summaryLabel">Produto</span>
                  <strong>{values.fruitName} · {values.variety}</strong>
                  <p>{values.quality}</p>
                </div>
                <div className="studio-summaryCard">
                  <span className="studio-summaryLabel">Precificação</span>
                  <strong>{values.minPrice} - {values.maxPrice}</strong>
                  <p>{summaryPriceSpread}</p>
                </div>
                <div className="studio-summaryCard">
                  <span className="studio-summaryLabel">Certificações</span>
                  <strong>{certifications.length}</strong>
                  <p>Selecionadas com chips animados</p>
                </div>
                <div className="studio-summaryCard">
                  <span className="studio-summaryLabel">Status</span>
                  <strong>{publishState === 'loading' ? 'Publicando...' : publishState === 'success' ? 'Publicado' : 'Pronto'}</strong>
                  <p>{publishState === 'success' ? 'Concluído com animação premium' : 'Revisão final antes do envio'}</p>
                </div>
              </div>
            </section>
          </div>

          <footer className="studio-footerActions">
            <button type="button" className="studio-button studio-buttonSecondary" onClick={goBack} disabled={stepIndex === 0}>Voltar</button>
            <button type="button" className="studio-button studio-buttonGhost" onClick={goNext} disabled={stepIndex === STEP_DEFINITIONS.length - 1}>Próximo</button>
            <button type="button" className="studio-button studio-buttonPrimary" onClick={() => void handlePublish()}>
              {publishState === 'loading' ? 'Publicando...' : 'Publicar anúncio'}
            </button>
          </footer>
          {publishState === 'success' ? <div className="studio-successToast">Anúncio publicado com sucesso.</div> : null}
        </article>

        <aside className="studio-previewPanel">
          <div className="studio-previewPanelHeader">
            <span className="studio-previewLabel">Preview ao vivo</span>
            <strong>{completion}% concluído</strong>
          </div>
          <div className="studio-liveCard">
            <div className="studio-liveImage">{imagePreview ? <img src={imagePreview} alt="Pré-visualização otimizada do produto" /> : <div>Preview</div>}</div>
            <div className="studio-liveMeta">
              <h4>{values.fruitName}</h4>
              <p>{values.variety} · {values.quality}</p>
              <div className="studio-chipRow studio-chipRowCompact">
                {certifications.slice(0, 3).map((certification) => (
                  <span key={certification} className="studio-statusChip">{certification}</span>
                ))}
              </div>
            </div>
          </div>

          <div className="studio-previewStats">
            <div><span>Faixa</span><strong>{values.minPrice}</strong></div>
            <div><span>Kg</span><strong>{values.pricePerKg}</strong></div>
            <div><span>Caixa</span><strong>{values.pricePerBox}</strong></div>
            <div><span>Estoque</span><strong>{values.availableQuantity}</strong></div>
          </div>

          <div className="studio-previewNotes">
            <div className="studio-note">
              <strong>Estado visual</strong>
              <p>Hover, focus, error, success e loading presentes em toda a superfície interativa.</p>
            </div>
            <div className="studio-note">
              <strong>Performance</strong>
              <p>Componentes isolados, re-render mínimo e layout pronto para escalar para mobile nativo.</p>
            </div>
          </div>
        </aside>
      </div>

      {confetti.length ? (
        <div className="studio-confetti" aria-hidden="true">
          {confetti.map((piece) => (
            <span key={piece.id} className="studio-confettiPiece" style={{ left: piece.left, animationDelay: piece.delay, background: `hsl(${piece.hue} 100% 68%)` }} />
          ))}
        </div>
      ) : null}
    </section>
  );
}