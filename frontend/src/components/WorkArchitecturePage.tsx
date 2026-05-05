import { useState } from 'react';

import { generateWorkArchitecture, type AiJobStatus, type WorkArchitecture } from '../api';
import AiJobStatusBar from './common/AiJobStatusBar';

export default function WorkArchitecturePage() {
  const [draft, setDraft] = useState({
    objective: '',
    scope: '',
    horizon: '',
    participants: '',
    constraints: '',
    use_memory: true,
  });
  const [result, setResult] = useState<WorkArchitecture | null>(null);
  const [message, setMessage] = useState('');
  const [job, setJob] = useState<AiJobStatus | null>(null);

  async function generate() {
    setMessage('생성 중...');
    setJob({
      job_id: 'local-work-architecture',
      task: 'work_architecture',
      status: 'queued',
      actor: '',
      input_summary: draft.objective,
      used_sources: [],
      result_path: '',
      error: '',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
    try {
      setJob((current) => current ? { ...current, status: 'running', updated_at: new Date().toISOString() } : current);
      const next = await generateWorkArchitecture(draft);
      setResult(next);
      setJob(next.ai_job ?? null);
      setMessage(`저장됨: ${next.path}`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '업무 아키텍처 생성 실패');
      setJob((current) =>
        current
          ? {
              ...current,
              status: 'failed',
              error: err instanceof Error ? err.message : '업무 아키텍처 생성 실패',
              updated_at: new Date().toISOString(),
            }
          : current,
      );
    }
  }

  return (
    <section className="page-grid">
      <div className="panel">
        <p className="eyebrow">Work Architecture</p>
        <h2>회사 진행 업무 아키텍처 생성</h2>
        <div className="memory-form">
          <input placeholder="목적" value={draft.objective} onChange={(event) => setDraft({ ...draft, objective: event.target.value })} />
          <textarea placeholder="범위" value={draft.scope} onChange={(event) => setDraft({ ...draft, scope: event.target.value })} />
          <input placeholder="기간" value={draft.horizon} onChange={(event) => setDraft({ ...draft, horizon: event.target.value })} />
          <textarea placeholder="참여자" value={draft.participants} onChange={(event) => setDraft({ ...draft, participants: event.target.value })} />
          <textarea placeholder="제약" value={draft.constraints} onChange={(event) => setDraft({ ...draft, constraints: event.target.value })} />
          <label>
            <input type="checkbox" checked={draft.use_memory} onChange={(event) => setDraft({ ...draft, use_memory: event.target.checked })} />
            저장된 메모리 사용
          </label>
          <button type="button" onClick={() => void generate()}>업무 아키텍처 생성</button>
          {message ? <p className="muted">{message}</p> : null}
        </div>
        <AiJobStatusBar job={job} />
      </div>
      <div className="panel">
        <p className="eyebrow">Generated Plan</p>
        <h2>생성 결과</h2>
        <pre className="status-pre">{result?.markdown || '아직 생성된 업무 아키텍처가 없습니다.'}</pre>
      </div>
    </section>
  );
}
