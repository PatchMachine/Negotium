import { useEffect, useState } from 'react';

import {
  fetchLlmRuntime,
  fetchLocalLlmStatus,
  saveLlmRuntime,
  searchHuggingFaceModels,
  startLocalLlm,
  stopLocalLlm,
  uploadDocument,
  type HuggingFaceModelItem,
  type LocalLlmStatus,
  type LlmRuntime,
  type UploadRecord,
} from '../../api';
import LlmTaskRoutingPanel from '../ai/LlmTaskRoutingPanel';

const recommendedLocalModels = [
  {
    vendor: 'Qwen',
    name: 'Qwen3-4B',
    model: 'Qwen/Qwen3-4B',
    strength: '가벼운 로컬 기본 모델, 빠른 응답과 낮은 VRAM 부담',
  },
  {
    vendor: 'Qwen',
    name: 'Qwen3-8B',
    model: 'Qwen/Qwen3-8B',
    strength: 'Qwen 계열 상위 품질, 사내 문서/추론 작업 기본 후보',
  },
  {
    vendor: 'Qwen',
    name: 'Qwen2.5-7B-Instruct',
    model: 'Qwen/Qwen2.5-7B-Instruct',
    strength: '검증된 instruct 모델, 안정적인 한국어/업무 응답',
  },
  {
    vendor: 'LG',
    name: 'EXAONE 계열',
    model: 'LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct',
    strength: '국내 기업 모델 후보, 텍스트 업무 자동화 중심',
  },
  {
    vendor: '업스테이지',
    name: 'Solar 계열',
    model: 'upstage/SOLAR-10.7B-Instruct-v1.0',
    strength: '한국어 업무/문서 처리 후보, agentic 업무 실험용',
  },
];

export default function LocalAgentAdminPanel() {
  const [status, setStatus] = useState<LocalLlmStatus | null>(null);
  const [runtime, setRuntime] = useState<LlmRuntime | null>(null);
  const [query, setQuery] = useState('Qwen');
  const [hfModels, setHfModels] = useState<HuggingFaceModelItem[]>([]);
  const [selectedModel, setSelectedModel] = useState('');
  const [adapterModel, setAdapterModel] = useState('');
  const [uploadedAdapters, setUploadedAdapters] = useState<UploadRecord[]>([]);
  const [selectedUploadPath, setSelectedUploadPath] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  async function refresh() {
    try {
      const [nextStatus, nextRuntime] = await Promise.all([fetchLocalLlmStatus(), fetchLlmRuntime()]);
      setStatus(nextStatus);
      setRuntime(nextRuntime);
      setSelectedModel((current) => current || nextRuntime.local_model || nextStatus.model || 'Qwen/Qwen3-4B');
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

  async function searchModels() {
    setBusy(true);
    setMessage('');
    try {
      const payload = await searchHuggingFaceModels(query);
      setHfModels(payload.models);
      if (payload.models[0]) {
        setSelectedModel(payload.models[0].id);
      }
      setMessage(payload.models.length ? 'Hugging Face 모델 목록을 불러왔습니다.' : '검색 결과가 없습니다.');
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Hugging Face 모델 검색 실패');
    } finally {
      setBusy(false);
    }
  }

  async function saveLocalModel() {
    if (!runtime) return;
    const nextModel = (selectedUploadPath || adapterModel || selectedModel).trim();
    if (!nextModel) {
      setMessage('저장할 Hugging Face 모델 ID를 선택하거나 입력하세요.');
      return;
    }
    setBusy(true);
    setMessage('');
    try {
      const saved = await saveLlmRuntime({
        ...runtime,
        local_model: nextModel,
        local_enabled: false,
        default_route: 'local',
        default_provider: 'vllm',
      });
      setRuntime(saved);
      setStatus(await fetchLocalLlmStatus());
      setMessage(`로컬 모델 설정을 저장했습니다: ${nextModel}. Local ON을 누르면 이 모델로 로드됩니다.`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '로컬 모델 설정 저장 실패');
    } finally {
      setBusy(false);
    }
  }

  async function uploadAdapterFile(fileList: FileList | null) {
    const file = fileList?.[0];
    if (!file) return;
    setBusy(true);
    setMessage('');
    try {
      const form = new FormData();
      form.append('file', file);
      form.append('work_title', '로컬 에이전트 파인튜닝/LoRA 모델');
      form.append('tags', 'local_model,lora,finetune');
      form.append('description', '로컬 에이전트에서 선택 가능한 파인튜닝/LoRA 모델 파일');
      const saved = (await uploadDocument(form)).upload;
      setUploadedAdapters((current) => [saved, ...current]);
      setSelectedUploadPath(saved.path);
      setMessage(`업로드했습니다: ${saved.filename}. 로컬 모델 설정 저장을 누르면 이 파일 경로가 선택됩니다.`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '파인튜닝/LoRA 업로드 실패');
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
        <div className="panel-subsection">
          <h3>로컬 모델 선택</h3>
          <p className="muted">
            멀티모달 모델은 기본 후보에서 제외하고, 텍스트 기반 로컬 에이전트 모델을 우선 추천합니다.
            Qwen, LG EXAONE, Solar 계열을 기본으로 고르고 필요하면 Hugging Face에서 직접 검색하세요.
          </p>
          <div className="memory-form">
            <div className="recommended-model-grid">
              {recommendedLocalModels.map((item) => (
                <article
                  className={selectedModel === item.model ? 'model-card model-card-selected' : 'model-card'}
                  key={item.model}
                >
                  <small>{item.vendor}</small>
                  <strong>{item.name}</strong>
                  <p>{item.strength}</p>
                  <code>{item.model}</code>
                  <button className="secondary-button" type="button" onClick={() => {
                    setSelectedModel(item.model);
                    setSelectedUploadPath('');
                  }}>
                    기본 모델 선택
                  </button>
                </article>
              ))}
            </div>
            <label>
              Hugging Face 검색어
              <div className="inline-input-row">
                <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="예: LG EXAONE, Qwen, Korean LLM" />
                <button className="secondary-button" type="button" disabled={busy} onClick={() => void searchModels()}>
                  검색
                </button>
              </div>
            </label>
            <label>
              Base 모델 선택
              <select value={selectedModel} onChange={(event) => setSelectedModel(event.target.value)}>
                {[selectedModel, ...recommendedLocalModels.map((item) => item.model), ...hfModels.map((model) => model.id)]
                  .filter(Boolean)
                  .filter((model, index, arr) => arr.indexOf(model) === index)
                  .map((model) => (
                    <option key={model} value={model}>{model}</option>
                  ))}
              </select>
            </label>
            <label>
              파인튜닝 / LoRA Hugging Face repo ID
              <input
                value={adapterModel}
                onChange={(event) => setAdapterModel(event.target.value)}
                placeholder="예: organization/qwen3-4b-office-lora"
              />
            </label>
            <label>
              파인튜닝 / LoRA 파일 업로드
              <input
                type="file"
                accept=".safetensors,.bin,.pt,.pth,.gguf,.zip,.tar,.json"
                onChange={(event) => void uploadAdapterFile(event.target.files)}
              />
            </label>
            {uploadedAdapters.length ? (
              <label>
                업로드한 모델/어댑터 선택
                <select value={selectedUploadPath} onChange={(event) => setSelectedUploadPath(event.target.value)}>
                  <option value="">업로드 파일을 사용하지 않음</option>
                  {uploadedAdapters.map((upload) => (
                    <option key={upload.id} value={upload.path}>
                      {upload.filename} · {upload.path}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            {hfModels.length ? (
              <div className="log-list">
                {hfModels.slice(0, 5).map((model) => (
                  <article className="log-card" key={model.id}>
                    <strong>{model.id}</strong>
                    <p>downloads {model.downloads.toLocaleString()} · likes {model.likes.toLocaleString()}</p>
                    <button className="secondary-button" type="button" onClick={() => {
                      setSelectedModel(model.id);
                      setSelectedUploadPath('');
                    }}>
                      이 모델 선택
                    </button>
                  </article>
                ))}
              </div>
            ) : null}
            <button type="button" disabled={busy} onClick={() => void saveLocalModel()}>
              로컬 모델 설정 저장
            </button>
          </div>
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
