import { useEffect, useState } from 'react';

import { deleteApiKey, fetchApiKeys, saveApiKey, type ApiKeyInfo } from '../api';

export default function AdminSettingsPage() {
  const [providers, setProviders] = useState<ApiKeyInfo[]>([]);
  const [draft, setDraft] = useState({ provider: 'openai', api_key: '', model: '', base_url: '' });
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

  async function save() {
    const result = await saveApiKey(draft);
    setProviders(result.providers);
    setMessage('저장했습니다.');
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
            <select value={draft.provider} onChange={(event) => setDraft({ ...draft, provider: event.target.value })}>
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
            <input value={draft.model} onChange={(event) => setDraft({ ...draft, model: event.target.value })} />
          </label>
          <label>
            Base URL
            <input value={draft.base_url} onChange={(event) => setDraft({ ...draft, base_url: event.target.value })} />
          </label>
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
              <strong>{provider.provider}</strong>
              <p>{provider.configured ? provider.masked_value : '미설정'} · {provider.model || 'model -'}</p>
              <button className="secondary-button" type="button" onClick={() => void remove(provider.provider)}>삭제</button>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
