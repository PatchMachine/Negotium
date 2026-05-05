import { FormEvent, useState } from 'react';

import {
  createOfficeDocument,
  readArchiveDocument,
  type AiJobStatus,
  type GeneratedDocument,
  type OfficeDocumentRequest,
} from '../api';
import AiJobStatusBar from './common/AiJobStatusBar';

const emptyDocument: OfficeDocumentRequest = {
  document_type: 'meeting_minutes',
  title: '',
  source_text: '',
  audience: '',
};

export default function DocumentAutomationPage() {
  const [draft, setDraft] = useState<OfficeDocumentRequest>(emptyDocument);
  const [result, setResult] = useState<GeneratedDocument | null>(null);
  const [busy, setBusy] = useState(false);
  const [job, setJob] = useState<AiJobStatus | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setJob({
      job_id: 'local-document-generation',
      task: 'document_generation',
      status: 'queued',
      actor: '',
      input_summary: draft.title,
      used_sources: [],
      result_path: '',
      error: '',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
    try {
      setJob((current) => current ? { ...current, status: 'running', updated_at: new Date().toISOString() } : current);
      const next = await createOfficeDocument(draft);
      setResult(next);
      setJob(next.ai_job ?? null);
    } catch (err) {
      setJob((current) =>
        current
          ? {
              ...current,
              status: 'failed',
              error: err instanceof Error ? err.message : '문서 생성 실패',
              updated_at: new Date().toISOString(),
            }
          : current,
      );
    } finally {
      setBusy(false);
    }
  }

  async function openResult(path: string) {
    const doc = await readArchiveDocument(path);
    setResult({ title: path, markdown: doc.markdown, path });
  }

  return (
    <section className="page-grid">
      <div className="panel">
        <p className="eyebrow">Office Docs</p>
        <h2>문서 자동화</h2>
        <p className="muted">회의록, 보고서, 업무 요청서, PPT 초안을 Markdown으로 생성합니다.</p>
        <form className="memory-form" onSubmit={handleSubmit}>
          <label>
            문서 유형
            <select
              value={draft.document_type}
              onChange={(event) =>
                setDraft({
                  ...draft,
                  document_type: event.target.value as OfficeDocumentRequest['document_type'],
                })
              }
            >
              <option value="meeting_minutes">회의록</option>
              <option value="report_draft">보고서 초안</option>
              <option value="work_request">업무 요청서</option>
              <option value="ppt_outline">PPT 초안</option>
            </select>
          </label>
          <label>
            제목
            <input
              value={draft.title}
              placeholder="예: 5월 문서 자동화 도입 보고"
              onChange={(event) => setDraft({ ...draft, title: event.target.value })}
            />
          </label>
          <label>
            대상 독자
            <input
              value={draft.audience}
              placeholder="예: 대표, 관리팀, 신규 담당자"
              onChange={(event) => setDraft({ ...draft, audience: event.target.value })}
            />
          </label>
          <label>
            원문/메모
            <textarea
              value={draft.source_text}
              placeholder="회의 내용, 보고할 사실, 업무 요청 배경을 붙여넣으세요."
              onChange={(event) => setDraft({ ...draft, source_text: event.target.value })}
            />
          </label>
          <button disabled={busy} type="submit">{busy ? '생성 중...' : '문서 생성'}</button>
        </form>
        <AiJobStatusBar job={job} onOpenResult={(path) => void openResult(path)} />
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
