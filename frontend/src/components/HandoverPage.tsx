import { FormEvent, useState } from 'react';

import { createHandoverBrief, type AiJobStatus, type GeneratedDocument, type HandoverRequest } from '../api';
import AiJobStatusBar from './common/AiJobStatusBar';

const emptyHandover: HandoverRequest = {
  work_title: '',
  outgoing_owner: '',
  incoming_owner: '',
  notes: '',
};

export default function HandoverPage() {
  const [draft, setDraft] = useState<HandoverRequest>(emptyHandover);
  const [result, setResult] = useState<GeneratedDocument | null>(null);
  const [busy, setBusy] = useState(false);
  const [job, setJob] = useState<AiJobStatus | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setJob({
      job_id: 'local-handover',
      task: 'handover',
      status: 'queued',
      actor: '',
      input_summary: draft.work_title,
      used_sources: [],
      result_path: '',
      error: '',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
    try {
      setJob((current) => current ? { ...current, status: 'running', updated_at: new Date().toISOString() } : current);
      const next = await createHandoverBrief(draft);
      setResult(next);
      setJob(next.ai_job ?? null);
    } catch (err) {
      setJob((current) =>
        current
          ? {
              ...current,
              status: 'failed',
              error: err instanceof Error ? err.message : '인수인계 문서 생성 실패',
              updated_at: new Date().toISOString(),
            }
          : current,
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="page-grid">
      <div className="panel">
        <p className="eyebrow">Handover</p>
        <h2>인수인계 문서 생성</h2>
        <p className="muted">
          담당자가 바뀌거나 퇴사할 때 패치머신 영구메모리와 archive 로그를 바탕으로 직무 적응 문서를 만듭니다.
        </p>
        <form className="memory-form" onSubmit={handleSubmit}>
          <label>
            업무명
            <input
              value={draft.work_title}
              placeholder="예: Discord 문서 접수 자동화"
              onChange={(event) => setDraft({ ...draft, work_title: event.target.value })}
            />
          </label>
          <label>
            기존 담당자
            <input
              value={draft.outgoing_owner}
              onChange={(event) => setDraft({ ...draft, outgoing_owner: event.target.value })}
            />
          </label>
          <label>
            신규 담당자
            <input
              value={draft.incoming_owner}
              onChange={(event) => setDraft({ ...draft, incoming_owner: event.target.value })}
            />
          </label>
          <label>
            추가 메모
            <textarea
              value={draft.notes}
              placeholder="예: 최근 막힌 지점, 중요한 고객, 반복 실수"
              onChange={(event) => setDraft({ ...draft, notes: event.target.value })}
            />
          </label>
          <button disabled={busy} type="submit">{busy ? '생성 중...' : '인수인계 문서 생성'}</button>
        </form>
        <AiJobStatusBar job={job} />
      </div>
      <div className="panel">
        <p className="eyebrow">Generated</p>
        <h2>문서 결과</h2>
        {result ? (
          <>
            <p className="muted">저장 위치: {result.path}</p>
            <pre className="status-pre">{result.markdown}</pre>
          </>
        ) : (
          <p className="muted">아직 생성된 문서가 없습니다.</p>
        )}
      </div>
    </section>
  );
}
