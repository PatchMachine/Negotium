import { useEffect, useState } from 'react';

import { fetchProgress, type ProgressPayload } from '../api';

export default function ProgressLogPage() {
  const [progress, setProgress] = useState<ProgressPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      setProgress(await fetchProgress());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : '진행 로그 로드 실패');
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  return (
    <section className="page-grid">
      <div className="panel">
        <p className="eyebrow">Progress</p>
        <h2>진행 로그</h2>
        <button className="secondary-button" type="button" onClick={() => void refresh()}>
          새로고침
        </button>
        {error ? <p className="alert">{error}</p> : null}
        <pre className="status-pre">{progress?.current_status_md ?? '로딩 중...'}</pre>
      </div>

      <div className="panel">
        <p className="eyebrow">Archive</p>
        <h2>최근 처리 로그</h2>
        <div className="log-list">
          {progress?.recent_logs.map((log) => (
            <article className="log-card" key={log.path}>
              <strong>{log.title}</strong>
              <p>
                {log.repo || 'unknown repo'} · {log.status || 'unknown'} · {log.llm_route || 'route -'}
              </p>
              <small>{log.path}</small>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
