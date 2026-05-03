import { FormEvent, useState } from 'react';

import {
  createInterviewKit,
  createOnboardingPlan,
  createRoleRequirements,
  type GeneratedDocument,
  type HiringRequest,
} from '../api';

const emptyHiring: HiringRequest = {
  role_title: '',
  business_need: '',
  priority: 'normal',
};

export default function HiringPage() {
  const [draft, setDraft] = useState<HiringRequest>(emptyHiring);
  const [result, setResult] = useState<GeneratedDocument | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  async function generate(action: 'requirements' | 'interview' | 'onboarding') {
    setBusy(action);
    try {
      const next =
        action === 'requirements'
          ? await createRoleRequirements(draft)
          : action === 'interview'
            ? await createInterviewKit(draft)
            : await createOnboardingPlan(draft);
      setResult(next);
    } finally {
      setBusy(null);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void generate('requirements');
  }

  return (
    <section className="page-grid">
      <div className="panel">
        <p className="eyebrow">Hiring BPA</p>
        <h2>채용/면접 키트 생성</h2>
        <p className="muted">
          회사 메모리와 현재 업무 계획을 바탕으로 직무 요구사항, 면접 질문, 온보딩 계획을 생성합니다.
        </p>
        <form className="memory-form" onSubmit={handleSubmit}>
          <label>
            직무명
            <input
              value={draft.role_title}
              placeholder="예: 회사 서류 자동화 담당자"
              onChange={(event) => setDraft({ ...draft, role_title: event.target.value })}
            />
          </label>
          <label>
            필요한 업무/비즈니스 상황
            <textarea
              value={draft.business_need}
              placeholder="예: Discord로 들어오는 문서를 분류하고 처리 흐름을 자동화해야 함"
              onChange={(event) => setDraft({ ...draft, business_need: event.target.value })}
            />
          </label>
          <label>
            우선순위
            <select
              value={draft.priority}
              onChange={(event) => setDraft({ ...draft, priority: event.target.value })}
            >
              <option value="low">low</option>
              <option value="normal">normal</option>
              <option value="high">high</option>
              <option value="urgent">urgent</option>
            </select>
          </label>
          <div className="form-actions">
            <button disabled={!!busy} type="submit">요구사항 생성</button>
            <button disabled={!!busy} type="button" onClick={() => void generate('interview')}>
              면접 키트 생성
            </button>
            <button disabled={!!busy} type="button" onClick={() => void generate('onboarding')}>
              온보딩 계획 생성
            </button>
          </div>
        </form>
      </div>
      <GeneratedDocumentPanel result={result} />
    </section>
  );
}

function GeneratedDocumentPanel({ result }: { result: GeneratedDocument | null }) {
  return (
    <div className="panel">
      <p className="eyebrow">Generated</p>
      <h2>생성 결과</h2>
      {result ? (
        <>
          <p className="muted">저장 위치: {result.path}</p>
          <pre className="status-pre">{result.markdown}</pre>
        </>
      ) : (
        <p className="muted">아직 생성된 문서가 없습니다.</p>
      )}
    </div>
  );
}
