import { useState } from 'react';

export default function HrEvaluationPage() {
  const [draft, setDraft] = useState({
    employee: '',
    period: '',
    criteria: '',
    evidence: '',
  });
  const [preview, setPreview] = useState('');

  function generatePreview() {
    setPreview(
      [
        `# 인사평가 초안: ${draft.employee || '평가 대상자'}`,
        '',
        `- 평가 기간: ${draft.period || '(미입력)'}`,
        `- 평가 기준: ${draft.criteria || '(미입력)'}`,
        '',
        '## 성과 근거',
        draft.evidence || '(성과 메모를 입력하세요.)',
        '',
        '## 확인 필요',
        '- 실제 평가 반영 전 관리자 검토가 필요합니다.',
        '- 향후 패치에서 패치머신 영구메모리/업무 로그 기반 자동 초안 생성과 연결할 수 있습니다.',
      ].join('\n'),
    );
  }

  return (
    <section className="page-grid">
      <div className="panel">
        <p className="eyebrow">HR evaluation</p>
        <h2>인사평가</h2>
        <p className="muted">
          관리자 전용 평가 초안 공간입니다. 현재는 입력 기반 초안이며, 이후 업무 로그와 패치머신 메모리를 연결해 자동 평가 초안을 생성할 수 있습니다.
        </p>
        <div className="memory-form">
          <input
            placeholder="평가 대상자"
            value={draft.employee}
            onChange={(event) => setDraft({ ...draft, employee: event.target.value })}
          />
          <input
            placeholder="평가 기간 (예: 2026 Q2)"
            value={draft.period}
            onChange={(event) => setDraft({ ...draft, period: event.target.value })}
          />
          <textarea
            placeholder="평가 기준"
            value={draft.criteria}
            onChange={(event) => setDraft({ ...draft, criteria: event.target.value })}
          />
          <textarea
            placeholder="성과/근거 메모"
            value={draft.evidence}
            onChange={(event) => setDraft({ ...draft, evidence: event.target.value })}
          />
          <button type="button" onClick={generatePreview}>
            평가 초안 생성
          </button>
        </div>
      </div>
      <div className="panel">
        <p className="eyebrow">Draft</p>
        <h2>평가 초안 미리보기</h2>
        <pre>{preview || '아직 생성된 초안이 없습니다.'}</pre>
      </div>
    </section>
  );
}
