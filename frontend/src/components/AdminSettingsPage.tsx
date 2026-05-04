import { useEffect, useState } from 'react';

import {
  deleteApiKey,
  fetchContextFirewallAudit,
  fetchContextFirewallPolicy,
  fetchApiKeys,
  fetchProviderModels,
  previewProviderModels,
  saveApiKey,
  sanitizeContextFirewall,
  type ApiKeyInfo,
  type ContextFirewallAuditRecord,
  type ContextFirewallDecision,
  type ProviderModelPayload,
} from '../api';
import LocalAgentAdminPanel from './admin/LocalAgentAdminPanel';

export default function AdminSettingsPage() {
  const [providers, setProviders] = useState<ApiKeyInfo[]>([]);
  const [draft, setDraft] = useState({ provider: 'openai', api_key: '', model: '' });
  const [models, setModels] = useState<ProviderModelPayload | null>(null);
  const [message, setMessage] = useState('');

  async function refresh() {
    try {
      setProviders((await fetchApiKeys()).providers);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'API 키 목록 로드 실패');
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  useEffect(() => {
    async function loadModels() {
      try {
        const next = await fetchProviderModels(draft.provider);
        setModels(next);
        setDraft((current) => ({ ...current, model: current.model || next.models[0] || '' }));
      } catch (err) {
        setModels(null);
        setMessage(err instanceof Error ? err.message : '모델 목록 로드 실패');
      }
    }
    void loadModels();
  }, [draft.provider]);

  async function save() {
    const result = await saveApiKey(draft);
    setProviders(result.providers);
    setMessage('저장했습니다.');
  }

  async function previewModels() {
    try {
      const next = await previewProviderModels(draft.provider, draft.api_key);
      setModels(next);
      setDraft((current) => ({ ...current, model: next.models[0] || current.model }));
      setMessage(next.source === 'live' ? '입력한 API 키로 모델 목록을 확인했습니다.' : `기본 추천 목록: ${next.reason}`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '모델 목록 확인 실패');
    }
  }

  async function remove(provider: string) {
    const result = await deleteApiKey(provider);
    setProviders(result.providers);
  }

  return (
    <section className="page-grid">
      <div className="panel">
        <p className="eyebrow">Frontier API</p>
        <h2>API 키 설정</h2>
        <div className="memory-form">
          <label>
            Provider
            <select
              value={draft.provider}
              onChange={(event) => setDraft({ provider: event.target.value, api_key: draft.api_key, model: '' })}
            >
              <option value="openai">OpenAI / GPT</option>
              <option value="anthropic">Anthropic / Claude</option>
              <option value="gemini">Google / Gemini</option>
              <option value="vllm">vLLM / Local</option>
            </select>
          </label>
          <label>
            API Key
            <input type="password" value={draft.api_key} onChange={(event) => setDraft({ ...draft, api_key: event.target.value })} />
          </label>
          <label>
            Model
            <select value={draft.model} onChange={(event) => setDraft({ ...draft, model: event.target.value })}>
              {(models?.models.length ? models.models : [draft.model].filter(Boolean)).map((model) => (
                <option key={model} value={model}>{model}</option>
              ))}
            </select>
          </label>
          {models ? (
            <p className="muted">
              모델 목록: {models.source === 'live' ? '실시간 API' : '기본 추천 목록'}
              {models.reason ? ` · ${models.reason}` : ''}
            </p>
          ) : null}
          <button className="secondary-button" type="button" onClick={() => void previewModels()}>
            입력한 키로 모델 목록 확인
          </button>
          <button type="button" onClick={() => void save()}>암호화 저장</button>
          {message ? <p className="muted">{message}</p> : null}
        </div>
      </div>
      <div className="panel">
        <p className="eyebrow">Configured</p>
        <h2>저장된 Provider</h2>
        <div className="log-list">
          {providers.map((provider) => (
            <article className="log-card" key={provider.provider}>
              <strong>{provider.label || provider.provider}</strong>
              <p>{provider.configured ? provider.masked_value : '미설정'} · {provider.model || 'model -'}</p>
              <p className="muted">Base URL은 시스템 기본값 사용: {provider.base_url || '-'}</p>
              <button className="secondary-button" type="button" onClick={() => void remove(provider.provider)}>삭제</button>
            </article>
          ))}
        </div>
      </div>
      <LocalAgentAdminPanel />
      <ContextFirewallPanel />
    </section>
  );
}

function ContextFirewallPanel() {
  const [sample, setSample] = useState(
    'A고객 김민준 팀장 token abc.def.ghi postgres://admin:pass@10.0.3.2:5432/payments',
  );
  const [result, setResult] = useState<ContextFirewallDecision | null>(null);
  const [audit, setAudit] = useState<ContextFirewallAuditRecord[]>([]);
  const [policy, setPolicy] = useState<Record<string, unknown> | null>(null);
  const [message, setMessage] = useState('');

  async function refresh() {
    try {
      const [nextPolicy, nextAudit] = await Promise.all([
        fetchContextFirewallPolicy(),
        fetchContextFirewallAudit().catch(() => ({ records: [], count: 0 })),
      ]);
      setPolicy(nextPolicy.policy);
      setAudit(nextAudit.records);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Context Firewall 로드 실패');
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function runRedactionTest() {
    try {
      const payload = await sanitizeContextFirewall({
        destination: 'frontier_llm',
        task_type: 'admin_redaction_test',
        content: sample,
      });
      setResult(payload.result);
      await refresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Context Firewall 테스트 실패');
    }
  }

  return (
    <div className="panel">
      <p className="eyebrow">Context Firewall</p>
      <h2>로컬 검열 / 외부 LLM 반출 제어</h2>
      <p className="muted">
        외부 프론티어 LLM으로 나가기 전 secret, PII, 사내 경로 정책, prompt injection을 검사하고 감사 로그를 남깁니다.
      </p>
      <div className="memory-form">
        <label>
          Redaction 테스트 입력
          <textarea value={sample} onChange={(event) => setSample(event.target.value)} />
        </label>
        <button type="button" onClick={() => void runRedactionTest()}>Context Firewall 테스트</button>
        {message ? <p className="muted">{message}</p> : null}
      </div>
      {result ? (
        <div className="log-card">
          <strong>{result.decision} · {result.highest_sensitivity}</strong>
          <p>removed: {JSON.stringify(result.removed_counts)}</p>
          <pre>{JSON.stringify(result.sanitized, null, 2)}</pre>
        </div>
      ) : null}
      <details>
        <summary>Effective Policy</summary>
        <pre>{JSON.stringify(policy, null, 2)}</pre>
      </details>
      <details open>
        <summary>Recent Context Firewall Audit</summary>
        <div className="log-list">
          {audit.slice(0, 8).map((record) => (
            <article className="log-card" key={record.id}>
              <strong>{record.decision} · {record.highest_sensitivity}</strong>
              <p>{record.destination} · {record.task_type}</p>
              <small>{record.detectors_triggered.join(', ') || 'detectors -'} · {record.redacted_context_hash}</small>
            </article>
          ))}
          {!audit.length ? <p className="muted small">아직 Context Firewall audit 기록이 없습니다.</p> : null}
        </div>
      </details>
    </div>
  );
}
