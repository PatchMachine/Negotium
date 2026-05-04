import { useEffect, useState } from 'react';

import {
  fetchLlmRuntime,
  saveLlmRuntime,
  type LlmProviderName,
  type LlmRuntime,
  type LlmRuntimeRoute,
  type LlmTaskRoute,
} from '../../api';

const PROVIDERS: LlmProviderName[] = ['vllm', 'openai', 'anthropic', 'gemini', 'fake'];

const TASKS: Array<{ id: string; label: string; description: string }> = [
  { id: 'memory_summary', label: 'AI 가독 정보 요약', description: '패치머신 영구메모리와 작업 기억을 읽기 좋게 요약' },
  { id: 'agent_planning', label: '에이전트 실행계획', description: '작업 목표를 승인 가능한 실행 단계로 분해' },
  { id: 'document_generation', label: '문서 자동화', description: '보고서, 회의록, 업무 요청서 등 회사 문서 생성' },
  { id: 'hiring', label: '채용/면접', description: '직무 요구사항, 면접 질문, 온보딩 문서 생성' },
  { id: 'handover', label: '인수인계', description: '담당자 변경 시 업무 맥락과 다음 액션 정리' },
  { id: 'chat', label: '테스트 채팅', description: '관리자가 LLM 응답과 연결 상태를 시험' },
];

function defaultTaskRoute(runtime: LlmRuntime): LlmTaskRoute {
  return {
    route: runtime.default_route,
    provider: runtime.default_provider,
    model: '',
  };
}

export default function LlmTaskRoutingPanel() {
  const [runtime, setRuntime] = useState<LlmRuntime | null>(null);
  const [message, setMessage] = useState('');

  async function refresh() {
    try {
      setRuntime(await fetchLlmRuntime());
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'LLM 작업 설정 로드 실패');
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function updateTask(taskId: string, patch: Partial<LlmTaskRoute>) {
    if (!runtime) return;
    const current = runtime.task_routes?.[taskId] || defaultTaskRoute(runtime);
    const next: LlmRuntime = {
      ...runtime,
      task_routes: {
        ...(runtime.task_routes || {}),
        [taskId]: {
          ...current,
          ...patch,
        },
      },
    };
    setRuntime(next);
    const saved = await saveLlmRuntime(next);
    setRuntime(saved);
    setMessage('작업별 LLM 설정을 저장했습니다.');
  }

  return (
    <section className="panel llm-task-routing-panel">
      <p className="eyebrow">LLM task routing</p>
      <h2>LLM 작업 설정</h2>
      <p className="muted small">
        어떤 작업을 로컬 LLM 또는 API LLM 중 어디에 맡길지 정합니다. 회사 기밀이 들어가는 작업은 local/vLLM을 우선으로 둘 수 있습니다.
      </p>
      {!runtime ? <p className="muted">설정을 불러오는 중입니다.</p> : null}
      {runtime ? (
        <div className="llm-task-table" role="table" aria-label="작업별 LLM 설정">
          {TASKS.map((task) => {
            const route = runtime.task_routes?.[task.id] || defaultTaskRoute(runtime);
            return (
              <div className="llm-task-row" role="row" key={task.id}>
                <div className="llm-task-copy">
                  <strong>{task.label}</strong>
                  <span className="muted small">{task.description}</span>
                </div>
                <label>
                  Route
                  <select
                    value={route.route}
                    onChange={(e) => void updateTask(task.id, { route: e.target.value as LlmRuntimeRoute })}
                  >
                    <option value="local">local</option>
                    <option value="api">api</option>
                  </select>
                </label>
                <label>
                  Provider
                  <select
                    value={route.provider}
                    onChange={(e) => void updateTask(task.id, { provider: e.target.value as LlmProviderName })}
                  >
                    {PROVIDERS.map((provider) => (
                      <option key={provider} value={provider}>
                        {provider}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Model memo
                  <input
                    placeholder="예: gpt-4.1-mini"
                    value={route.model || ''}
                    onChange={(e) => void updateTask(task.id, { model: e.target.value })}
                  />
                </label>
              </div>
            );
          })}
        </div>
      ) : null}
      {message ? <p className="muted">{message}</p> : null}
    </section>
  );
}
