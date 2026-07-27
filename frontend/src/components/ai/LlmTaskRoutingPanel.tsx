import { useEffect, useMemo, useState } from 'react';

import {
  fetchLlmProviders,
  fetchLlmRuntime,
  fetchProviderModels,
  saveLlmRuntime,
  type LlmProviderName,
  type LlmRuntime,
  type LlmRuntimeRoute,
  type LlmTaskRoute,
  type ModelProfile,
  type ModelTier,
} from '../../api';
import { TierBadge, TieredModelOptions } from './ModelTier';

// `fake` is a test-only provider and `vllm` is the local route, so both stay
// hardcoded; every real cloud provider comes from the backend catalog.
const EXTRA_PROVIDERS: LlmProviderName[] = ['vllm', 'fake'];

const FALLBACK_CLOUD_PROVIDERS: LlmProviderName[] = [
  'solar',
  'openai',
  'anthropic',
  'gemini',
  'together',
];

/**
 * Which tier each task is best served by. Used to flag a routing choice that
 * will underperform (e.g. an agent task pinned to a general-tier model).
 */
const TASKS: Array<{ id: string; label: string; description: string; preferredTier: ModelTier }> = [
  {
    id: 'memory_summary',
    label: 'AI 가독 정보 요약',
    description: '네고티움 영구메모리와 작업 기억을 읽기 좋게 요약',
    preferredTier: 'reasoning',
  },
  {
    id: 'agent_planning',
    label: '에이전트 실행계획',
    description: '작업 목표를 승인 가능한 실행 단계로 분해',
    preferredTier: 'agent',
  },
  {
    id: 'document_generation',
    label: '문서 자동화',
    description: '보고서, 회의록, 업무 요청서 등 회사 문서 생성',
    preferredTier: 'reasoning',
  },
  {
    id: 'hiring',
    label: '채용/면접',
    description: '직무 요구사항, 면접 질문, 온보딩 문서 생성',
    preferredTier: 'reasoning',
  },
  {
    id: 'handover',
    label: '인수인계',
    description: '담당자 변경 시 업무 맥락과 다음 액션 정리',
    preferredTier: 'reasoning',
  },
  {
    id: 'chat',
    label: 'AI 어시스턴트',
    description: '메모리 기반 실시간 채팅',
    preferredTier: 'general',
  },
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
  const [providerModels, setProviderModels] = useState<Record<string, string[]>>({});
  const [profiles, setProfiles] = useState<Map<string, ModelProfile>>(new Map());
  const [cloudProviders, setCloudProviders] =
    useState<LlmProviderName[]>(FALLBACK_CLOUD_PROVIDERS);

  const providerOptions = useMemo(
    () => ['vllm', ...cloudProviders.filter((item) => item !== 'vllm'), 'fake'] as LlmProviderName[],
    [cloudProviders],
  );

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

  useEffect(() => {
    async function loadProviders() {
      try {
        const payload = await fetchLlmProviders();
        const names = payload.providers
          .map((item) => item.provider as LlmProviderName)
          .filter((item) => !EXTRA_PROVIDERS.includes(item));
        if (names.length) setCloudProviders(names);
      } catch {
        setCloudProviders(FALLBACK_CLOUD_PROVIDERS);
      }
    }
    void loadProviders();
  }, []);

  // Local (vLLM) model choices and their tier metadata come from the catalog
  // rather than a second hardcoded list.
  useEffect(() => {
    void ensureProviderModels('vllm');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function ensureProviderModels(provider: LlmProviderName) {
    if (providerModels[provider]?.length) return;
    try {
      const payload = await fetchProviderModels(provider);
      setProviderModels((current) => ({ ...current, [provider]: payload.models }));
      setProfiles((current) => {
        const next = new Map(current);
        for (const profile of payload.model_profiles || []) {
          next.set(`${provider}:${profile.id}`, profile);
        }
        return next;
      });
    } catch {
      setProviderModels((current) => ({ ...current, [provider]: [] }));
    }
  }

  async function updateTask(taskId: string, patch: Partial<LlmTaskRoute>) {
    if (!runtime) return;
    const current = runtime.task_routes?.[taskId] || defaultTaskRoute(runtime);
    const nextRoute = { ...current, ...patch };
    if (patch.provider && patch.provider !== current.provider) {
      void ensureProviderModels(patch.provider);
    }
    const next: LlmRuntime = {
      ...runtime,
      task_routes: {
        ...(runtime.task_routes || {}),
        [taskId]: nextRoute,
      },
    };
    setRuntime(next);
    const saved = await saveLlmRuntime(next);
    setRuntime(saved);
    setMessage('작업별 LLM 설정을 저장했습니다. 선택한 모델이 실제 추론에 반영됩니다.');
  }

  const localOptions = useMemo(() => {
    const base = runtime?.local_model ? [runtime.local_model] : [];
    const catalogLocal = providerModels.vllm || [];
    return [...base, ...catalogLocal].filter((model, index, arr) => arr.indexOf(model) === index);
  }, [runtime?.local_model, providerModels.vllm]);

  function providerFor(route: LlmTaskRoute): LlmProviderName {
    return route.route === 'local' || route.provider === 'vllm' ? 'vllm' : route.provider;
  }

  function modelOptionsFor(route: LlmTaskRoute): string[] {
    if (route.route === 'local' || route.provider === 'vllm') {
      return localOptions;
    }
    return providerModels[route.provider] || [];
  }

  /** Profiles for one route, keyed by bare model id for `TieredModelOptions`. */
  function profilesFor(route: LlmTaskRoute): Map<string, ModelProfile> {
    const provider = providerFor(route);
    const scoped = new Map<string, ModelProfile>();
    for (const [key, profile] of profiles) {
      if (key.startsWith(`${provider}:`)) scoped.set(profile.id, profile);
    }
    return scoped;
  }

  return (
    <section className="panel llm-task-routing-panel">
      <p className="eyebrow">LLM task routing</p>
      <h2>LLM 작업 설정</h2>
      <p className="muted small">
        작업별 route·provider·모델을 지정합니다. 모델을 비우면 provider 기본값(또는 로컬 모델 설정)을 사용합니다.
      </p>
      {!runtime ? <p className="muted">설정을 불러오는 중입니다.</p> : null}
      {runtime ? (
        <div className="llm-task-table" role="table" aria-label="작업별 LLM 설정">
          {TASKS.map((task) => {
            const route = runtime.task_routes?.[task.id] || defaultTaskRoute(runtime);
            const options = modelOptionsFor(route);
            const routeProfiles = profilesFor(route);
            const selectedProfile = route.model ? routeProfiles.get(route.model) : undefined;
            // Only warn when we actually know the model's tier — an empty model
            // means "provider default" and an unlisted one is simply unknown.
            const tierMismatch =
              selectedProfile &&
              task.preferredTier === 'agent' &&
              !selectedProfile.supports_tools;
            return (
              <div className="llm-task-row" role="row" key={task.id}>
                <div className="llm-task-copy">
                  <strong>{task.label}</strong>
                  <span className="muted small">{task.description}</span>
                  <span className="muted small">
                    권장 <TierBadge tier={task.preferredTier} />
                    {selectedProfile ? (
                      <>
                        {' · 현재 '}
                        <TierBadge tier={selectedProfile.tier} label={selectedProfile.tier_label} />
                      </>
                    ) : null}
                  </span>
                  {tierMismatch ? (
                    <span className="muted small llm-task-warning">
                      이 모델은 도구 호출을 지원하지 않아 에이전트 실행계획 품질이 떨어집니다.
                    </span>
                  ) : null}
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
                    onFocus={() => void ensureProviderModels(route.provider)}
                    onChange={(e) => {
                      const provider = e.target.value as LlmProviderName;
                      void ensureProviderModels(provider);
                      void updateTask(task.id, { provider, model: '' });
                    }}
                  >
                    {providerOptions.map((provider) => (
                      <option key={provider} value={provider}>
                        {provider}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Model
                  <select
                    value={route.model || ''}
                    onFocus={() => void ensureProviderModels(route.provider)}
                    onChange={(e) => void updateTask(task.id, { model: e.target.value })}
                  >
                    <option value="">(기본값 사용)</option>
                    <TieredModelOptions models={options} profiles={routeProfiles} />
                  </select>
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
