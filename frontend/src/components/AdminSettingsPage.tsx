import { useEffect, useState } from 'react';

import {
  deleteApiKey,
  fetchApiKeys,
  fetchProviderModels,
  previewProviderModels,
  saveApiKey,
  type ApiKeyInfo,
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
    </section>
  );
}
