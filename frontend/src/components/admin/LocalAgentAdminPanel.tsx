import { useEffect, useState } from 'react';

import {
  fetchLocalLlmStatus,
  startLocalLlm,
  stopLocalLlm,
  type LocalLlmStatus,
} from '../../api';
import LlmTaskRoutingPanel from '../ai/LlmTaskRoutingPanel';

export default function LocalAgentAdminPanel() {
  const [status, setStatus] = useState<LocalLlmStatus | null>(null);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  async function refresh() {
    try {
      setStatus(await fetchLocalLlmStatus());
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '로컬 에이전트 상태 조회 실패');
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function toggleLocal() {
    setBusy(true);
    setMessage('');
    try {
      const next = status?.enabled ? await stopLocalLlm() : await startLocalLlm();
      setStatus(next);
      setMessage(status?.enabled ? '로컬 에이전트를 중지했습니다.' : '로컬 에이전트 기동을 요청했습니다.');
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '로컬 에이전트 제어 실패');
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <section className="panel">
        <p className="eyebrow">Local agent admin</p>
        <h2>로컬 에이전트 관리 및 LLM 작업기능 제약</h2>
        <p className="muted">
          로컬 LLM 기동/중지는 서버 리소스와 보안에 직접 영향을 주므로 관리자만 수행합니다.
          일반 사용자는 AI 에이전트 페이지에서 상태만 확인합니다.
        </p>
        <div className={`local-llm-status local-llm-status-${status?.state || 'unknown'}`}>
          <div>
            <p className="eyebrow">Local LLM</p>
            <strong>{status?.message || '로컬 에이전트 상태를 불러오는 중입니다.'}</strong>
            <p className="muted">
              {status?.model || 'model -'} · {status?.mode || 'mode -'}
              {status?.ready_at ? ` · ready ${new Date(status.ready_at).toLocaleTimeString()}` : ''}
            </p>
            {status?.error ? <p className="alert">{status.error}</p> : null}
          </div>
          <span className="status-pill">{status?.state || 'unknown'}</span>
        </div>
        <div className="form-actions">
          <button type="button" disabled={busy} onClick={() => void toggleLocal()}>
            {status?.enabled ? 'Local OFF' : 'Local ON'}
          </button>
          <button type="button" className="secondary-button" onClick={() => void refresh()}>
            상태 새로고침
          </button>
        </div>
        {message ? <p className="muted">{message}</p> : null}
      </section>
      <LlmTaskRoutingPanel />
    </>
  );
}
