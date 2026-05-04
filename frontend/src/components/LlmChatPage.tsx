import { FormEvent, useEffect, useState } from 'react';

import {
  fetchLlmRuntime,
  fetchLocalLlmStatus,
  saveLlmRuntime,
  sendChatMessage,
  startLocalLlm,
  stopLocalLlm,
  type ChatResponse,
  type LocalLlmStatus,
  type LlmProviderName,
  type LlmRuntime,
  type LlmRuntimeRoute,
} from '../api';

const providerOptions: LlmProviderName[] = ['vllm', 'openai', 'anthropic', 'gemini', 'fake'];

export default function LlmChatPage() {
  const [runtime, setRuntime] = useState<LlmRuntime | null>(null);
  const [localStatus, setLocalStatus] = useState<LocalLlmStatus | null>(null);
  const [message, setMessage] = useState('');
  const [route, setRoute] = useState<LlmRuntimeRoute>('local');
  const [provider, setProvider] = useState<LlmProviderName>('vllm');
  const [history, setHistory] = useState<Array<{ question: string; response: ChatResponse }>>([]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    void refreshRuntime();
  }, []);

  useEffect(() => {
    if (localStatus?.state !== 'loading' && localStatus?.state !== 'running') {
      return undefined;
    }
    const timer = window.setInterval(() => {
      void refreshLocalStatus();
    }, 2500);
    return () => window.clearInterval(timer);
  }, [localStatus?.state]);

  async function refreshRuntime() {
    try {
      const [nextRuntime, nextStatus] = await Promise.all([
        fetchLlmRuntime(),
        fetchLocalLlmStatus(),
      ]);
      setRuntime(nextRuntime);
      setLocalStatus(nextStatus);
      setRoute(nextRuntime.default_route);
      setProvider(nextRuntime.default_provider);
    } catch (err: unknown) {
      setNotice(err instanceof Error ? err.message : '런타임 로드 실패');
    }
  }

  async function refreshLocalStatus() {
    try {
      setLocalStatus(await fetchLocalLlmStatus());
    } catch (err: unknown) {
      setNotice(err instanceof Error ? err.message : '로컬 LLM 상태 조회 실패');
    }
  }

  async function toggleApiRuntime() {
    if (!runtime) return;
    const saved = await saveLlmRuntime({ ...runtime, api_enabled: !runtime.api_enabled });
    setRuntime(saved);
  }

  async function toggleLocalRuntime() {
    if (localStatus?.state === 'unavailable') {
      setNotice(localStatus.message);
      return;
    }
    setBusy(true);
    setNotice(null);
    try {
      const nextStatus = localStatus?.enabled ? await stopLocalLlm() : await startLocalLlm();
      setLocalStatus(nextStatus);
      const nextRuntime = await fetchLlmRuntime();
      setRuntime(nextRuntime);
      if (nextStatus.enabled) {
        setRoute('local');
        setProvider('vllm');
      }
    } catch (err) {
      setNotice(err instanceof Error ? err.message : '로컬 LLM 제어 실패');
    } finally {
      setBusy(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!message.trim()) return;
    setBusy(true);
    setNotice(null);
    try {
      const response = await sendChatMessage(message, route, provider);
      setHistory([{ question: message, response }, ...history]);
      setMessage('');
    } catch (err) {
      setNotice(err instanceof Error ? err.message : '채팅 호출 실패');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="page-grid">
      <div className="panel">
        <p className="eyebrow">LLM Chat</p>
        <h2>패치머신 영구메모리 기반 채팅</h2>
        <p className="muted">
          패치머신 영구메모리(`operations_memory.json`), 현재 상태, 최근 archive 로그를 컨텍스트로 넣어 답변합니다.
        </p>

        <div className="switch-row">
          <button type="button" className="secondary-button" onClick={() => void toggleLocalRuntime()}>
            Local {localStatus?.enabled ? 'ON' : 'OFF'}
          </button>
          <button type="button" className="secondary-button" onClick={() => void toggleApiRuntime()}>
            API {runtime?.api_enabled ? 'ON' : 'OFF'}
          </button>
          <button type="button" className="secondary-button" onClick={() => void refreshRuntime()}>
            상태 새로고침
          </button>
        </div>

        <div className={`local-llm-status local-llm-status-${localStatus?.state || 'unknown'}`}>
          <div>
            <p className="eyebrow">Local LLM</p>
            <strong>{localStatus?.message || '로컬 LLM 상태를 불러오는 중입니다.'}</strong>
            <p className="muted">
              {localStatus?.model || runtime?.local_model || 'Qwen/Qwen3-4B'} · {localStatus?.mode || 'embedded'}
              {localStatus?.ready_at ? ` · ready ${new Date(localStatus.ready_at).toLocaleTimeString()}` : ''}
            </p>
            {localStatus?.error ? <p className="alert">{localStatus.error}</p> : null}
          </div>
          <span className="status-pill">{localStatus?.state || 'unknown'}</span>
        </div>

        <form className="memory-form" onSubmit={handleSubmit}>
          <label>
            Route
            <select value={route} onChange={(event) => setRoute(event.target.value as LlmRuntimeRoute)}>
              <option value="local">local</option>
              <option value="api">api</option>
            </select>
          </label>
          <label>
            Provider
            <select value={provider} onChange={(event) => setProvider(event.target.value as LlmProviderName)}>
              {providerOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
          <label>
            질문
            <textarea
              value={message}
              placeholder="예: 청우식품 문서 자동화 업무의 다음 액션을 알려줘"
              onChange={(event) => setMessage(event.target.value)}
            />
          </label>
          <button disabled={busy} type="submit">
            {busy ? '호출 중...' : 'LLM 채팅 보내기'}
          </button>
        </form>
        {notice ? <p className="alert">{notice}</p> : null}
      </div>

      <div className="panel">
        <p className="eyebrow">Responses</p>
        <h2>채팅 로그</h2>
        <div className="log-list">
          {history.length === 0 ? <p className="muted">아직 채팅 기록이 없습니다.</p> : null}
          {history.map((entry, index) => (
            <article className="log-card" key={`${entry.question}-${index}`}>
              <strong>Q. {entry.question}</strong>
              <p>{entry.response.answer || '(빈 응답)'}</p>
              <small>
                {entry.response.route} / {entry.response.provider} / {entry.response.model || 'unknown'}
              </small>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
