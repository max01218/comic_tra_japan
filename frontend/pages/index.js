import Head from 'next/head';
import { useState, useEffect, useRef } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const FEATURES = [
  { icon: '🤖', title: 'AI 精準 OCR', desc: 'MangaOCR + EasyOCR 雙引擎偵測日文文字框' },
  { icon: '🦙', title: 'Sakura 14B 翻譯', desc: '本地端 LLM，無費用、無隱私疑慮的高品質翻譯' },
  { icon: '🎨', title: '智慧去字修圖', desc: '精準像素遮罩，去字時完美保留漫畫背景細節' },
  { icon: '📝', title: '自適應排版', desc: '智慧直書/橫書判斷，白色描邊確保任何背景皆清晰' },
];

export default function Home() {
  const [url, setUrl] = useState('');
  const [jobId, setJobId] = useState(null);
  const [jobStatus, setJobStatus] = useState(null);
  const [images, setImages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const pollRef = useRef(null);
  const viewerRef = useRef(null);

  const startTranslation = async () => {
    if (!url.trim()) return;
    setIsLoading(true);
    setError(null);
    setImages([]);
    setJobId(null);
    setJobStatus(null);

    try {
      const res = await fetch(`${API_BASE}/translate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url.trim() }),
      });
      if (!res.ok) throw new Error(`伺服器錯誤：${res.status}`);
      const data = await res.json();
      setJobId(data.job_id);
      setJobStatus('downloading');
    } catch (e) {
      setError(e.message);
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (!jobId) return;

    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE}/status/${jobId}`);
        const data = await res.json();
        setJobStatus(data.status);

        if (data.status === 'completed') {
          clearInterval(pollRef.current);
          setIsLoading(false);
          setImages(data.result_images || []);
          setTimeout(() => viewerRef.current?.scrollIntoView({ behavior: 'smooth' }), 200);
        } else if (data.status === 'failed') {
          clearInterval(pollRef.current);
          setIsLoading(false);
          setError(data.error || '翻譯任務失敗');
        }
      } catch (e) {
        setError('無法連線至後端伺服器，請確認 Python 後端已啟動。');
        clearInterval(pollRef.current);
        setIsLoading(false);
      }
    };

    pollRef.current = setInterval(poll, 3000);
    poll();

    return () => clearInterval(pollRef.current);
  }, [jobId]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !isLoading) startTranslation();
  };

  const getStatusInfo = () => {
    if (!jobStatus) return null;
    if (jobStatus === 'completed') return { type: 'completed', label: '翻譯完成', message: `成功處理 ${images.length} 頁漫畫！` };
    if (jobStatus === 'failed') return { type: 'error', label: '發生錯誤', message: error };
    if (jobStatus === 'downloading') return { type: 'processing', label: '翻譯中', message: '📥 正在下載漫畫圖片...' };
    return { type: 'processing', label: '翻譯中', message: `⚙️ ${jobStatus}` };
  };

  const statusInfo = getStatusInfo();

  return (
    <>
      <Head>
        <title>MangaTrans — AI 漫畫自動漢化引擎</title>
        <meta name="description" content="輸入漫畫網址，使用本地 Sakura 14B AI 模型自動偵測、翻譯並排版，打造專業品質的繁體中文漫畫！" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📖</text></svg>" />
      </Head>

      {/* NAVBAR */}
      <nav className="navbar">
        <a href="/" className="nav-logo">
          <div className="nav-logo-icon">📖</div>
          <span>MangaTrans</span>
        </a>
        <span className="nav-tag">Sakura 14B × Ollama</span>
      </nav>

      <div className="page-container">
        {/* HERO */}
        <section className="hero">
          <div className="hero-badge">
            <span className="dot" />
            Powered by Local AI · 100% 免費 · 注重隱私
          </div>

          <h1 className="hero-title">
            日漫自動翻成中文<br />就這麼簡單
          </h1>
          <p className="hero-subtitle">
            貼上漫畫網址，AI 自動完成 OCR 偵測、精準去字、高品質翻譯與直書排版，全流程一鍵搞定。
          </p>

          {/* INPUT CARD */}
          <div className="input-card">
            <label className="input-label" htmlFor="comic-url">漫畫網址</label>
            <div className="input-row">
              <input
                id="comic-url"
                className="url-input"
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="https://wnacg.com/photos-index-aid-xxxxxx.html"
                disabled={isLoading}
                autoComplete="off"
              />
              <button
                className="translate-btn"
                onClick={startTranslation}
                disabled={isLoading || !url.trim()}
                id="translate-button"
              >
                <span className="btn-icon">⚡</span>
                {isLoading ? '翻譯中...' : '開始翻譯'}
              </button>
            </div>
          </div>

          {/* STATUS CARD */}
          {statusInfo && (
            <div className="status-section">
              <div className={`status-card ${statusInfo.type}`}>
                {statusInfo.type === 'processing' ? (
                  <div className="spinner"><div className="spinner-ring" /></div>
                ) : (
                  <span style={{ fontSize: '1.8rem' }}>
                    {statusInfo.type === 'completed' ? '✅' : '❌'}
                  </span>
                )}
                <div className="status-text">
                  <div className={`status-label ${statusInfo.type}`}>{statusInfo.label}</div>
                  <div className="status-message">{statusInfo.message}</div>
                </div>
              </div>
            </div>
          )}

          {/* FEATURE CHIPS */}
          <div className="features-section">
            {FEATURES.map((f) => (
              <div className="feature-chip" key={f.title}>
                <span className="feature-icon">{f.icon}</span>
                <div className="feature-info">
                  <h4>{f.title}</h4>
                  <p>{f.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* VIEWER */}
        {images.length > 0 && (
          <section className="viewer-section" ref={viewerRef}>
            <div className="viewer-header">
              <h2 className="viewer-title">
                📚 翻譯成果
              </h2>
              <span className="viewer-count">{images.length} 頁</span>
            </div>
            <div className="manga-grid">
              {images.map((src, idx) => (
                <div
                  key={src}
                  className="manga-page-wrapper"
                  style={{ animationDelay: `${idx * 80}ms` }}
                >
                  <img
                    className="manga-page-img"
                    src={`${API_BASE}${src}`}
                    alt={`第 ${idx + 1} 頁`}
                    loading="lazy"
                  />
                  <span className="page-number">P{idx + 1}</span>
                </div>
              ))}
            </div>
          </section>
        )}
      </div>
    </>
  );
}
