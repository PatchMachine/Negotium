import { FormEvent, useEffect, useState } from 'react';

import {
  fetchAgentPlans,
  fetchLlmRuntime,
  fetchLocalLlmStatus,
  sendChatMessage,
  type AgentPlan,
  type ChatResponse,
  type LocalLlmStatus,
  type LlmProviderName,
  type LlmRuntime,
  type LlmRuntimeRoute,
} from '../../api';
import AgentPlansPanel from '../memory/AgentPlansPanel';
import PatchOpsCockpit from './PatchOpsCockpit';

const providerOptions: LlmProviderName[] = ['vllm', 'openai', 'anthropic', 'gemini', 'fake'];

export default function AiAgentPage() {
  const [plans, setPlans] = useState<AgentPlan[]>([]);
  const [agentObjective, setAgentObjective] = useState('');
  const [runtime, setRuntime] = useState<LlmRuntime | null>(null);
  const [localStatus, setLocalStatus] = useState<LocalLlmStatus | null>(null);
  const [message, setMessage] = useState('');
  const [route, setRoute] = useState<LlmRuntimeRoute>('local');
  const [provider, setProvider] = useState<LlmProviderName>('vllm');
  const [history, setHistory] = useState<Array<{ question: string; response: ChatResponse }>>([]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  async function refreshPlans() {
    try {
      setPlans((await fetchAgentPlans()).plans);
    } catch (err) {
      setNotice(err instanceof Error ? err.message : '에이전트 계획 로드 실패');
    }
  }

  async function refreshRuntime() {
    try {
      const [nextRuntime, nextStatus] = await Promise.all([fetchLlmRuntime(), fetchLocalLlmStatus()]);
      setRuntime(nextRuntime);
      setLocalStatus(nextStatus);
      const chatRoute = nextRuntime.task_routes?.chat;
      setRoute(chatRoute?.route || nextRuntime.default_route);
      setProvider(chatRoute?.provider || nextRuntime.default_provider);
    } catch (err) {
      setNotice(err instanceof Error ? err.message : '런타임 로드 실패');
    }
  }

  useEffect(() => {
    void refreshPlans();
    void refreshRuntime();
  }, []);

  useEffect(() => {
    if (localStatus?.state !== 'loading' && localStatus?.state !== 'running') {
      return undefined;
    }
    const timer = window.setInterval(() => {
      void fetchLocalLlmStatus().then(setLocalStatus).catch(() => undefined);
    }, 2500);
    return () => window.clearInterval(timer);
  }, [localStatus?.state]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!message.trim()) return;
    setBusy(true);
    setNotice(null);
    try {
      const response = await sendChatMessage(message, route, provider, 'chat');
      setHistory([{ question: message, response }, ...history]);
      setMessage('');
    } catch (err) {
      setNotice(err instanceof Error ? err.message : '테스트 채팅 호출 실패');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="ai-agent-layout">
      <div className="panel ai-agent-hero">
        <p className="eyebrow">AI agent operations</p>
        <h2>AI 에이전트 실행계획</h2>
        <p className="muted">
          AI를 단순 채팅창으로 쓰지 않고, 승인 가능한 실행계획과 작업별 LLM 선택 기준으로 운영합니다.
        </p>
        <div className="switch-row">
          <button type="button" className="secondary-button" onClick={() => void refreshRuntime()}>
            LLM 상태 새로고침
          </button>
          <span className="status-pill">Local {localStatus?.state || 'unknown'}</span>
        </div>
        <p className="muted small">로컬 모델 기동/중지는 관리자 메뉴의 “로컬 에이전트 관리”에서만 수행합니다.</p>
        {runtime ? (
          <p className="muted small">
            기본값: {runtime.default_route} / {runtime.default_provider} · 로컬 모델 {runtime.local_model}
          </p>
        ) : null}
      </div>

      <AgentPlansPanel
        plans={plans}
        agentObjective={agentObjective}
        setAgentObjective={setAgentObjective}
        onMessage={setNotice}
        onRefresh={() => refreshPlans()}
      />

      <PatchOpsCockpit onMessage={setNotice} />

      <details className="panel ai-test-chat-panel">
        <summary>테스트 채팅 (LLM 연결 확인용)</summary>
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
            테스트 질문
            <textarea
              value={message}
              placeholder="예: 다음 실행계획을 어떤 LLM으로 처리하면 좋을지 설명해줘"
              onChange={(event) => setMessage(event.target.value)}
            />
          </label>
          <button disabled={busy} type="submit">
            {busy ? '호출 중...' : '테스트 채팅 보내기'}
          </button>
        </form>
        <div className="log-list">
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
      </details>

      {notice ? <p className="alert">{notice}</p> : null}
    </section>
  );
}
