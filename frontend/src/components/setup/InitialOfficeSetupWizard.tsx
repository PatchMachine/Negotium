import { ChangeEvent, useState } from 'react';

import {
  analyzeInitialOfficeSetup,
  applyInitialOfficeSetup,
  fetchLlmRuntime,
  previewProviderModels,
  saveApiKey,
  saveLlmRuntime,
  setupAdmin,
  uploadDocument,
  type AuthUser,
  type CompanyProfile,
  type InitialOfficeSetupResult,
  type LlmProviderName,
  type PatchNoteRecommendationItem,
  type UploadRecord,
} from '../../api';
import { setSessionToken } from '../../auth';

type Props = {
  onAuthenticated: (user: AuthUser) => void;
};

type Step = 'admin' | 'llm' | 'profile' | 'files' | 'analyze' | 'review';
type LlmChoice = 'local' | 'api';
type ReviewSection = 'memory' | 'agents' | 'templates' | 'workflows' | 'security' | 'integrations' | 'routes';

export default function InitialOfficeSetupWizard({ onAuthenticated }: Props) {
  const [step, setStep] = useState<Step>('admin');
  const [admin, setAdmin] = useState({ user_id: '', display_name: '', title: '시스템 관리자', password: '' });
  const [sessionUser, setSessionUser] = useState<AuthUser | null>(null);
  const [llmChoice, setLlmChoice] = useState<LlmChoice>('local');
  const [provider, setProvider] = useState<LlmProviderName>('openai');
  const [apiKey, setApiKey] = useState('');
  const [model, setModel] = useState('');
  const [companyProfile, setCompanyProfile] = useState<CompanyProfile>({
    organization_size: 'startup',
    industries: ['it_saas'],
    departments: ['product_dev_it', 'cs'],
    primary_goals: ['meeting_notes', 'action_items', 'weekly_patch_notes', 'release_notes', 'integrated_search'],
    data_sensitivity: ['general'],
    deployment_preference: 'local_recommended',
  });
  const [uploads, setUploads] = useState<UploadRecord[]>([]);
  const [message, setMessage] = useState('');
  const [result, setResult] = useState<InitialOfficeSetupResult | null>(null);
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [apiRiskAccepted, setApiRiskAccepted] = useState(false);
  const [applySections, setApplySections] = useState<Record<ReviewSection, boolean>>({
    memory: true,
    agents: true,
    templates: true,
    workflows: true,
    security: true,
    integrations: true,
    routes: true,
  });

  async function createAdmin() {
    setBusy(true);
    setNotice('');
    try {
      const session = await setupAdmin(admin);
      setSessionToken(session.token);
      setSessionUser(session.user);
      setStep('llm');
    } catch (err) {
      setNotice(err instanceof Error ? err.message : '관리자 생성 실패');
    } finally {
      setBusy(false);
    }
  }

  async function configureLlm() {
    setBusy(true);
    setNotice('');
    try {
      const runtime = await fetchLlmRuntime();
      if (llmChoice === 'api') {
        if (!apiRiskAccepted) {
          setNotice('API 모델을 사용하려면 민감정보 외부 전송 가능성 경고를 확인해야 합니다.');
          return;
        }
        await saveApiKey({ provider, api_key: apiKey, model });
        await saveLlmRuntime({
          ...runtime,
          local_enabled: runtime.local_enabled,
          api_enabled: true,
          default_route: 'api',
          default_provider: provider,
          task_routes: {
            ...(runtime.task_routes || {}),
            memory_summary: { route: 'api', provider, model },
            document_generation: { route: 'api', provider, model },
            chat: { route: 'api', provider, model },
          },
        });
      } else {
        await saveLlmRuntime({
          ...runtime,
          local_enabled: true,
          api_enabled: runtime.api_enabled,
          default_route: 'local',
          default_provider: 'vllm',
          task_routes: {
            ...(runtime.task_routes || {}),
            memory_summary: { route: 'local', provider: 'vllm', model: runtime.local_model || 'Qwen/Qwen3-4B' },
            document_generation: { route: 'local', provider: 'vllm', model: runtime.local_model || 'Qwen/Qwen3-4B' },
            chat: { route: 'local', provider: 'vllm', model: runtime.local_model || 'Qwen/Qwen3-4B' },
          },
        });
      }
      setStep('profile');
    } catch (err) {
      setNotice(err instanceof Error ? err.message : 'LLM 설정 실패');
    } finally {
      setBusy(false);
    }
  }

  async function loadModels() {
    try {
      const payload = await previewProviderModels(provider, apiKey);
      setModel(payload.models[0] || model);
      setNotice(payload.source === 'live' ? '입력한 키로 모델 목록을 확인했습니다.' : payload.reason);
    } catch (err) {
      setNotice(err instanceof Error ? err.message : '모델 확인 실패');
    }
  }

  async function uploadFiles(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files || []);
    if (files.length === 0) return;
    setBusy(true);
    setNotice('');
    try {
      const saved: UploadRecord[] = [];
      for (const file of files) {
        const form = new FormData();
        form.append('file', file);
        form.append('work_title', '초기 오피스 세팅');
        form.append('tags', 'initial_setup');
        form.append('description', '첫 실행 오피스 세팅 파일');
        saved.push((await uploadDocument(form)).upload);
      }
      setUploads((current) => [...saved, ...current]);
    } catch (err) {
      setNotice(err instanceof Error ? err.message : '파일 업로드 실패');
    } finally {
      setBusy(false);
    }
  }

  async function analyze() {
    setBusy(true);
    setNotice('');
    try {
      const analyzed = await analyzeInitialOfficeSetup({
        message,
        upload_ids: uploads.map((upload) => upload.id),
        intent: 'initial_office_setup',
        company_profile: companyProfile,
      });
      setResult(analyzed);
      setStep('review');
    } catch (err) {
      setNotice(err instanceof Error ? err.message : 'AI 초기 세팅 분석 실패');
    } finally {
      setBusy(false);
    }
  }

  async function apply() {
    if (!result || !sessionUser) return;
    setBusy(true);
    setNotice('');
    try {
      await applyInitialOfficeSetup(approvedResult(result, applySections));
      onAuthenticated(sessionUser);
    } catch (err) {
      setNotice(err instanceof Error ? err.message : '초기 세팅 적용 실패');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-layout setup-layout">
      <section className="panel setup-wizard">
        <img className="auth-logo" src="/patchmachine-logo.png" alt="Patch Machine" />
        <p className="eyebrow">First-run office setup</p>
        <h1>패치머신 초기 오피스 세팅</h1>
        <StepBar step={step} />
        {step === 'admin' ? (
          <div className="memory-form">
            <input placeholder="관리자 ID" value={admin.user_id} onChange={(e) => setAdmin({ ...admin, user_id: e.target.value })} />
            <input placeholder="표시 이름" value={admin.display_name} onChange={(e) => setAdmin({ ...admin, display_name: e.target.value })} />
            <input placeholder="직함" value={admin.title} onChange={(e) => setAdmin({ ...admin, title: e.target.value })} />
            <input type="password" placeholder="비밀번호" value={admin.password} onChange={(e) => setAdmin({ ...admin, password: e.target.value })} />
            <button type="button" disabled={busy} onClick={() => void createAdmin()}>관리자 생성 후 계속</button>
          </div>
        ) : null}

        {step === 'llm' ? (
          <div className="memory-form">
            <div className="local-llm-status">
              <div>
                <strong>민감정보 보호 기본 권장: 로컬 에이전트 서버</strong>
                <p className="muted">인사 정보, 고객 정보, 계약서, 내부 운영 문서는 사내 서버/GPU에서 처리하는 로컬 에이전트를 권장합니다.</p>
              </div>
              <span className="status-pill">recommended</span>
            </div>
            <label className="checkbox-inline">
              <input type="radio" checked={llmChoice === 'local'} onChange={() => setLlmChoice('local')} />
              로컬 에이전트 사용
            </label>
            <label className="checkbox-inline">
              <input type="radio" checked={llmChoice === 'api'} onChange={() => setLlmChoice('api')} />
              API 모델 사용
            </label>
            {llmChoice === 'api' ? (
              <>
                <select value={provider} onChange={(e) => setProvider(e.target.value as LlmProviderName)}>
                  <option value="openai">OpenAI / GPT</option>
                  <option value="anthropic">Anthropic / Claude</option>
                  <option value="gemini">Google / Gemini</option>
                </select>
                <input type="password" placeholder="API Key" value={apiKey} onChange={(e) => setApiKey(e.target.value)} />
                <input placeholder="Model" value={model} onChange={(e) => setModel(e.target.value)} />
                <button className="secondary-button" type="button" onClick={() => void loadModels()}>입력한 키로 모델 확인</button>
                <label className="checkbox-inline">
                  <input type="checkbox" checked={apiRiskAccepted} onChange={(e) => setApiRiskAccepted(e.target.checked)} />
                  민감정보가 포함된 파일은 외부 API로 전송될 수 있음을 확인했습니다.
                </label>
              </>
            ) : null}
            <button type="button" disabled={busy} onClick={() => void configureLlm()}>LLM 설정 저장 후 계속</button>
          </div>
        ) : null}

        {step === 'profile' ? (
          <div className="memory-form">
            <p className="muted">회사 규모, 업종, 부서, 데이터 민감도를 고르면 AI가 계정에 맞는 Patch Note 에이전트와 템플릿을 조립합니다.</p>
            <select value={companyProfile.organization_size} onChange={(e) => setCompanyProfile({ ...companyProfile, organization_size: e.target.value })}>
              <option value="solo">1인/프리랜서</option>
              <option value="startup">스타트업/소규모 팀</option>
              <option value="smb">중소기업</option>
              <option value="mid_market">중견기업</option>
              <option value="enterprise_public">대기업/공공기관</option>
            </select>
            <select value={companyProfile.deployment_preference} onChange={(e) => setCompanyProfile({ ...companyProfile, deployment_preference: e.target.value })}>
              <option value="local_recommended">민감정보 보호: 로컬 에이전트 권장</option>
              <option value="api_allowed">API 모델 사용 허용</option>
              <option value="private_required">프라이빗/온프레미스 필요</option>
            </select>
            <OptionGroup
              title="업종"
              values={companyProfile.industries}
              options={[
                ['it_saas', 'IT/SaaS'],
                ['b2b_sales_cs', 'B2B 영업/CS'],
                ['professional_services', '전문서비스'],
                ['manufacturing', '제조'],
                ['construction', '건설'],
                ['ecommerce', '도소매/이커머스'],
                ['finance', '금융'],
                ['healthcare', '의료/복지'],
                ['public', '공공'],
                ['education', '교육'],
              ]}
              onChange={(values) => setCompanyProfile({ ...companyProfile, industries: values })}
            />
            <OptionGroup
              title="초기 타깃 부서"
              values={companyProfile.departments}
              options={[
                ['executive', '경영진'],
                ['hr', 'HR'],
                ['finance', '재무'],
                ['sales', '영업'],
                ['marketing', '마케팅'],
                ['cs', 'CS'],
                ['product_dev_it', '제품/개발/IT'],
                ['legal', '법무'],
                ['ops_procurement', '운영/구매'],
              ]}
              onChange={(values) => setCompanyProfile({ ...companyProfile, departments: values })}
            />
            <OptionGroup
              title="핵심 목적"
              values={companyProfile.primary_goals}
              options={[
                ['meeting_notes', 'AI 회의록'],
                ['action_items', '액션아이템 추출'],
                ['weekly_patch_notes', '팀 패치 노트'],
                ['release_notes', '릴리즈 노트 자동화'],
                ['integrated_search', '통합 검색'],
                ['customer_memory', '고객/프로젝트 메모리'],
                ['proposal_docs', '제안서/보고서'],
              ]}
              onChange={(values) => setCompanyProfile({ ...companyProfile, primary_goals: values })}
            />
            <OptionGroup
              title="데이터 민감도"
              values={companyProfile.data_sensitivity}
              options={[
                ['general', '일반 업무'],
                ['customer_info', '고객정보'],
                ['hr_info', '인사정보'],
                ['finance_info', '금융/재무정보'],
                ['medical_info', '의료정보'],
                ['trade_secret', '영업비밀'],
              ]}
              onChange={(values) => setCompanyProfile({ ...companyProfile, data_sensitivity: values })}
            />
            <button type="button" onClick={() => setStep('files')}>회사 프로파일 저장 후 계속</button>
          </div>
        ) : null}

        {step === 'files' ? (
          <div className="memory-form">
            <p className="muted">회사 인적 사항, 조직도, 운영 규정 파일을 올리면 AI가 초기 메모리와 사용자/직함 초안을 만듭니다.</p>
            <input type="file" multiple accept=".csv,.tsv,.xlsx,.txt,.md" onChange={(e) => void uploadFiles(e)} />
            <div className="log-list">
              {uploads.map((upload) => (
                <article className="log-card" key={upload.id}>
                  <strong>{upload.filename}</strong>
                  <small>{upload.path}</small>
                </article>
              ))}
            </div>
            <button type="button" onClick={() => setStep('analyze')}>파일 선택 완료</button>
          </div>
        ) : null}

        {step === 'analyze' ? (
          <div className="memory-form">
            <textarea
              value={message}
              placeholder="예: 이 엑셀 파일의 직함을 보고 부서/역할/초기 업무 메모리를 정리해줘"
              onChange={(e) => setMessage(e.target.value)}
            />
            <button type="button" disabled={busy} onClick={() => void analyze()}>AI로 초기 오피스 세팅 분석</button>
          </div>
        ) : null}

        {step === 'review' ? (
          <div className="memory-form">
            <p className="muted">AI가 만든 초안을 검토한 뒤 적용하세요. 직원 로그인 계정은 자동 생성하지 않습니다.</p>
            {result ? (
              <>
                <ReviewToggle id="memory" label="운영/작업 메모리 적용" checked={applySections.memory} onChange={(id, checked) => setApplySections({ ...applySections, [id]: checked })} />
                <article className="log-card">
                  <strong>{result.recommended_package}</strong>
                  <small>{JSON.stringify(result.workspace_profile)}</small>
                </article>
                <ReviewToggle id="agents" label="추천 에이전트 팩 적용" checked={applySections.agents} onChange={(id, checked) => setApplySections({ ...applySections, [id]: checked })} />
                <RecommendationList items={result.agent_packs} />
                <ReviewToggle id="templates" label="추천 템플릿 적용" checked={applySections.templates} onChange={(id, checked) => setApplySections({ ...applySections, [id]: checked })} />
                <RecommendationList items={result.templates} />
                <ReviewToggle id="workflows" label="추천 워크플로우 적용" checked={applySections.workflows} onChange={(id, checked) => setApplySections({ ...applySections, [id]: checked })} />
                <RecommendationList items={result.workflows} />
                <ReviewToggle id="security" label="보안 기본값 적용" checked={applySections.security} onChange={(id, checked) => setApplySections({ ...applySections, [id]: checked })} />
                <RecommendationList items={result.security_defaults} />
                <ReviewToggle id="integrations" label="연동 우선순위 적용" checked={applySections.integrations} onChange={(id, checked) => setApplySections({ ...applySections, [id]: checked })} />
                <RecommendationList items={result.integration_priorities} />
                <ReviewToggle id="routes" label="LLM 라우팅 추천 적용" checked={applySections.routes} onChange={(id, checked) => setApplySections({ ...applySections, [id]: checked })} />
                <pre>{JSON.stringify(result.llm_task_routes, null, 2)}</pre>
                <h3>첫 14일 실행안</h3>
                <ul>{result.first_14_days.map((item) => <li key={item}>{item}</li>)}</ul>
                <h3>사람 검토 필수</h3>
                <ul>{result.human_review_required.map((item) => <li key={item}>{item}</li>)}</ul>
              </>
            ) : null}
            <button type="button" disabled={busy} onClick={() => void apply()}>검토 완료 · 초기 세팅 적용</button>
          </div>
        ) : null}

        {notice ? <p className="alert">{notice}</p> : null}
      </section>
    </main>
  );
}

function StepBar({ step }: { step: Step }) {
  const steps: Array<[Step, string]> = [
    ['admin', '관리자'],
    ['llm', 'LLM'],
    ['profile', '프로파일'],
    ['files', '파일'],
    ['analyze', 'AI 분석'],
    ['review', '적용'],
  ];
  const activeIndex = steps.findIndex(([id]) => id === step);
  return (
    <div className="setup-steps" aria-label="초기 설정 단계">
      {steps.map(([id, label], index) => (
        <span key={id} className={index <= activeIndex ? 'setup-step active' : 'setup-step'}>
          {label}
        </span>
      ))}
    </div>
  );
}

function OptionGroup({
  title,
  values,
  options,
  onChange,
}: {
  title: string;
  values: string[];
  options: Array<[string, string]>;
  onChange: (values: string[]) => void;
}) {
  return (
    <fieldset className="setup-option-group">
      <legend>{title}</legend>
      {options.map(([id, label]) => (
        <label className="checkbox-inline" key={id}>
          <input
            type="checkbox"
            checked={values.includes(id)}
            onChange={(event) => {
              const next = event.target.checked ? [...values, id] : values.filter((value) => value !== id);
              onChange(next.length ? next : [id]);
            }}
          />
          {label}
        </label>
      ))}
    </fieldset>
  );
}

function ReviewToggle({
  id,
  label,
  checked,
  onChange,
}: {
  id: ReviewSection;
  label: string;
  checked: boolean;
  onChange: (id: ReviewSection, checked: boolean) => void;
}) {
  return (
    <label className="checkbox-inline">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(id, event.target.checked)}
      />
      {label}
    </label>
  );
}

function RecommendationList({ items }: { items: PatchNoteRecommendationItem[] }) {
  if (!items.length) {
    return <p className="muted">추천 항목 없음</p>;
  }
  return (
    <div className="log-list">
      {items.map((item) => (
        <article className="log-card" key={item.id || item.name}>
          <strong>{item.name || item.id}</strong>
          <small>{item.description || item.reason || item.priority || ''}</small>
        </article>
      ))}
    </div>
  );
}

function approvedResult(result: InitialOfficeSetupResult, sections: Record<ReviewSection, boolean>): InitialOfficeSetupResult {
  return {
    ...result,
    operations_memory: sections.memory ? result.operations_memory : {},
    work_memory: sections.memory ? result.work_memory : {},
    agent_packs: sections.agents ? result.agent_packs : [],
    templates: sections.templates ? result.templates : [],
    workflows: sections.workflows ? result.workflows : [],
    security_defaults: sections.security ? result.security_defaults : [],
    integration_priorities: sections.integrations ? result.integration_priorities : [],
    llm_task_routes: sections.routes ? result.llm_task_routes : {},
  };
}
