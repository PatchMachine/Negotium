import { useEffect, useMemo, useState } from 'react';

import { fetchProgress, type ProgressPayload } from '../api';

export default function ProgressLogPage() {
  const [progress, setProgress] = useState<ProgressPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState('all');

  const statusCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const log of progress?.recent_logs ?? []) {
      const status = log.status || 'unknown';
      counts.set(status, (counts.get(status) ?? 0) + 1);
    }
    return counts;
  }, [progress]);

  const filteredLogs = useMemo(() => {
    const logs = progress?.recent_logs ?? [];
    if (statusFilter === 'all') return logs;
    return logs.filter((log) => (log.status || 'unknown') === statusFilter);
  }, [progress, statusFilter]);

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
    <section className="page-workspace">
      <div className="workspace-hero">
        <div className="panel">
          <p className="eyebrow">업무 진행 상황</p>
          <h2>진행 로그</h2>
          <p className="muted">현재 상태와 최근 처리 기록을 한눈에 확인하고, 진행 상태별로 필요한 기록만 골라볼 수 있습니다.</p>
          <button className="secondary-button" type="button" onClick={() => void refresh()}>
            새로고침
          </button>
          {error ? <p className="alert">{error}</p> : null}
        </div>
        <div className="compact-stat-strip">
          <div className="compact-stat">
            <strong>{progress?.recent_logs.length ?? 0}</strong>
            <span>최근 기록</span>
          </div>
        </div>
      </div>

      <div className="workspace-split">
        <div className="panel workspace-sidebar">
          <div className="sticky-panel-header">
            <p className="eyebrow">현재 상태</p>
            <h2>현재 상태</h2>
          </div>
          <div className="bounded-preview">
            <pre>{progress?.current_status_md ?? '로딩 중...'}</pre>
          </div>
        </div>

        <div className="panel workspace-detail">
          <div className="sticky-panel-header">
            <p className="eyebrow">처리 기록</p>
            <h2>최근 처리 로그</h2>
            <div className="workspace-tabs" aria-label="Progress status filters">
              <button
                type="button"
                className={statusFilter === 'all' ? 'workspace-tab active' : 'workspace-tab'}
                onClick={() => setStatusFilter('all')}
              >
                전체 {progress?.recent_logs.length ?? 0}
              </button>
              {[...statusCounts.entries()].map(([status, count]) => (
                <button
                  type="button"
                  key={status}
                  className={statusFilter === status ? 'workspace-tab active' : 'workspace-tab'}
                  onClick={() => setStatusFilter(status)}
                >
                  {status} {count}
                </button>
              ))}
            </div>
          </div>
          <div className="compact-card-list bounded-list">
            {filteredLogs.map((log) => (
              <article className="log-card" key={log.path}>
                <strong>{log.title}</strong>
                <p>
                  {log.repo || 'unknown repo'} · {log.status || 'unknown'} · {log.llm_route || 'route -'}
                </p>
                <small>{log.path}</small>
              </article>
            ))}
            {!filteredLogs.length ? <p className="muted small">표시할 최근 처리 로그가 없습니다.</p> : null}
          </div>
        </div>
      </div>
    </section>
  );
}
