import { FormEvent, useState } from 'react';

import { readArchiveDocument, type DocumentRead, type ReadableContextBundle } from '../api';
import ReadableContextWorkbench from './memory/ReadableContextWorkbench';

const PRESETS = [
  'hr/interview_kits/20260505_025144_onboarding_plan_문서_관리_담당자.md',
  'hr/onboarding_plans/',
  'documents/',
  'work_architecture/',
  'patch_records/',
];

export default function DocumentsViewerPage() {
  const [path, setPath] = useState<string>('');
  const [doc, setDoc] = useState<DocumentRead | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [query, setQuery] = useState('');
  const [bundle, setBundle] = useState<ReadableContextBundle | null>(null);

  async function load(target: string) {
    if (!target.trim()) return;
    setLoading(true);
    setError('');
    try {
      const next = await readArchiveDocument(target.trim());
      setDoc(next);
      setPath(next.path);
    } catch (err) {
      setError(err instanceof Error ? err.message : '문서를 불러오지 못했습니다.');
      setDoc(null);
    } finally {
      setLoading(false);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await load(path);
  }

  return (
    <section className="page-grid">
      <ReadableContextWorkbench
        query={query}
        onQueryChange={setQuery}
        selectedIds={selectedIds}
        onSelectedIdsChange={setSelectedIds}
        onBundlePreview={setBundle}
      />
      <div className="panel">
        <p className="eyebrow">Archive viewer</p>
        <h2>문서 열람</h2>
        <p className="muted">
          archive/ 하위에 자동 생성된 markdown / json / yaml 문서를 안전하게 조회합니다. (예: HR 인터뷰 kit, 온보딩 계획,
          업무 아키텍처). 경로 traversal은 허용되지 않습니다.
        </p>
        <form className="connector-config-form" onSubmit={submit}>
          <label>
            archive 상대 경로
            <input
              type="text"
              value={path}
              placeholder="hr/interview_kits/20260505_025144_onboarding_plan_문서_관리_담당자.md"
              onChange={(event) => setPath(event.target.value)}
            />
          </label>
          <div className="switch-row">
            <button className="primary" type="submit" disabled={loading}>
              {loading ? '불러오는 중...' : '열람'}
            </button>
            {error ? <span className="status-pill warn">{error}</span> : null}
          </div>
        </form>
        <div className="switch-row" style={{ flexWrap: 'wrap', marginTop: '8px' }}>
          {PRESETS.map((preset) => (
            <button
              key={preset}
              type="button"
              className="secondary"
              onClick={() => {
                setPath(preset);
                if (preset.endsWith('.md')) {
                  void load(preset);
                }
              }}
            >
              {preset}
            </button>
          ))}
        </div>
      </div>
      {doc ? (
        <div className="panel">
          <p className="eyebrow">{doc.path}</p>
          <h2>문서 미리보기</h2>
          <p className="muted small">
            {doc.bytes.toLocaleString()} bytes · 수정 {doc.modified_at}
          </p>
          <div className="document-viewer">
            <pre>{doc.markdown}</pre>
          </div>
        </div>
      ) : null}
      {bundle ? (
        <div className="panel">
          <p className="eyebrow">AI readable bundle</p>
          <h2>AI가 읽을 정보 묶음</h2>
          <p className="muted small">
            내부 파일 {bundle.used_sources.length}개 · 휘발성 {bundle.volatile_memories.length}개 · 약{' '}
            {bundle.estimated_tokens.toLocaleString()} tokens
          </p>
          <div className="document-viewer">
            <pre>{bundle.markdown}</pre>
          </div>
        </div>
      ) : null}
    </section>
  );
}
