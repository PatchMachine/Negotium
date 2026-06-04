import { FormEvent, useEffect, useMemo, useState } from 'react';

import {
  createPatchRecord,
  fetchPatchRecord,
  fetchPatchRecords,
  type PatchRecord,
  type PatchRecordCreate,
  type PatchRecordDetail,
} from '../api';

const DEFAULT_FORM: PatchRecordCreate = {
  title: '',
  summary: '',
  request: '',
  plan: [],
  changed_files: [],
  verification: [],
  follow_ups: [],
  tags: [],
  agent: '',
};

const AGENT_PRESETS = [
  'cursor',
  'claude_code',
  'antigravity',
  'codex',
];

function parseLines(value: string): string[] {
  return value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);
}

export default function PatchRecordsPage() {
  const [records, setRecords] = useState<PatchRecord[]>([]);
  const [selected, setSelected] = useState<PatchRecordDetail | null>(null);
  const [form, setForm] = useState<PatchRecordCreate>(DEFAULT_FORM);
  const [planText, setPlanText] = useState('');
  const [changedText, setChangedText] = useState('');
  const [verificationText, setVerificationText] = useState('');
  const [followUpsText, setFollowUpsText] = useState('');
  const [tagsText, setTagsText] = useState('');
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [showComposer, setShowComposer] = useState(false);

  const filteredRecords = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return records;
    return records.filter((record) =>
      `${record.title} ${record.summary} ${record.actor} ${record.agent} ${record.created_at}`.toLowerCase().includes(needle),
    );
  }, [query, records]);

  async function refresh() {
    setError('');
    try {
      const next = await fetchPatchRecords();
      setRecords(next.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : '패치 기록을 불러오지 못했습니다.');
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function selectRecord(recordId: string) {
    setError('');
    try {
      const detail = await fetchPatchRecord(recordId);
      setSelected(detail);
    } catch (err) {
      setError(err instanceof Error ? err.message : '패치 기록을 불러오지 못했습니다.');
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form.title.trim()) {
      setError('title 은 필수입니다.');
      return;
    }
    setSaving(true);
    setMessage('');
    setError('');
    try {
      const next = await createPatchRecord({
        ...form,
        plan: parseLines(planText),
        changed_files: parseLines(changedText),
        verification: parseLines(verificationText),
        follow_ups: parseLines(followUpsText),
        tags: parseLines(tagsText),
      });
      setSelected(next);
      setMessage('패치 기록을 archive 에 저장했습니다.');
      setForm(DEFAULT_FORM);
      setPlanText('');
      setChangedText('');
      setVerificationText('');
      setFollowUpsText('');
      setTagsText('');
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : '저장에 실패했습니다.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="page-workspace">
      <div className="workspace-hero">
        <div className="panel">
          <p className="eyebrow">Coding agent log</p>
          <h2>패치 기록</h2>
          <p className="muted">
            코딩 에이전트가 읽고 후속 작업을 이어갈 수 있도록 archive/patch_records/* 에 markdown + JSONL index 로
            저장합니다. 기본 화면은 기록 탐색과 상세 열람에 집중합니다.
          </p>
          {error ? <p className="alert" role="alert">{error}</p> : null}
        </div>
        <div className="compact-stat-strip">
          <div className="compact-stat">
            <strong>{records.length}</strong>
            <span>Total records</span>
          </div>
          <div className="compact-stat">
            <strong>{new Set(records.map((record) => record.agent || 'unspecified')).size}</strong>
            <span>Agents</span>
          </div>
        </div>
      </div>

      <details className="advanced-panel" open={showComposer} onToggle={(event) => setShowComposer(event.currentTarget.open)}>
        <summary>새 패치 기록 작성</summary>
        <form className="connector-config-form" onSubmit={submit}>
          <label>
            제목
            <input type="text" value={form.title} required onChange={(event) => setForm({ ...form, title: event.target.value })} />
          </label>
          <label>
            담당 에이전트
            <input
              list="patch-record-agent-presets"
              type="text"
              value={form.agent}
              onChange={(event) => setForm({ ...form, agent: event.target.value })}
              placeholder="cursor / claude_code / antigravity / codex"
            />
            <datalist id="patch-record-agent-presets">
              {AGENT_PRESETS.map((preset) => (
                <option key={preset} value={preset} />
              ))}
            </datalist>
          </label>
          <label>
            요약
            <textarea value={form.summary} rows={2} onChange={(event) => setForm({ ...form, summary: event.target.value })} />
          </label>
          <label>
            요청 / 배경
            <textarea value={form.request} rows={3} onChange={(event) => setForm({ ...form, request: event.target.value })} />
          </label>
          <div className="connector-config-grid">
            <label>
              계획 (한 줄에 하나)
              <textarea value={planText} rows={3} onChange={(event) => setPlanText(event.target.value)} />
            </label>
            <label>
              변경 파일 (한 줄에 하나)
              <textarea value={changedText} rows={3} onChange={(event) => setChangedText(event.target.value)} />
            </label>
            <label>
              검증 결과 (한 줄에 하나)
              <textarea value={verificationText} rows={3} onChange={(event) => setVerificationText(event.target.value)} />
            </label>
            <label>
              후속 이슈 (한 줄에 하나)
              <textarea value={followUpsText} rows={3} onChange={(event) => setFollowUpsText(event.target.value)} />
            </label>
          </div>
          <label>
            태그 (한 줄에 하나)
            <textarea value={tagsText} rows={2} onChange={(event) => setTagsText(event.target.value)} />
          </label>
          <div className="switch-row">
            <button className="primary" type="submit" disabled={saving}>
              {saving ? '저장 중...' : '패치 기록 저장'}
            </button>
            {message ? <span className="status-pill success">{message}</span> : null}
          </div>
        </form>
      </details>

      <div className="workspace-split">
        <div className="panel workspace-sidebar">
          <div className="sticky-panel-header">
            <p className="eyebrow">Records</p>
            <h2>기록 목록</h2>
            <div className="memory-form row-compact">
              <input value={query} placeholder="제목, 요약, agent 검색" onChange={(event) => setQuery(event.target.value)} />
              <button type="button" onClick={() => void refresh()}>
                새로고침
              </button>
            </div>
          </div>
          <div className="compact-card-list bounded-list">
            {records.length === 0 ? <p className="muted small">아직 등록된 패치 기록이 없습니다.</p> : null}
            {filteredRecords.map((record) => (
              <button
                type="button"
                key={record.record_id}
                className={`compact-list-card${selected?.record_id === record.record_id ? ' selected' : ''}`}
                onClick={() => void selectRecord(record.record_id)}
              >
                <strong>{record.title}</strong>
                <span className="muted small">{record.summary || '요약 없음'}</span>
                <small>
                  {record.created_at} · {record.actor || 'system'} · {record.agent || 'agent 미지정'}
                </small>
              </button>
            ))}
          </div>
        </div>

        <div className="panel workspace-detail">
          {selected ? (
            <>
              <p className="eyebrow">{selected.relative_path}</p>
              <h2>{selected.title}</h2>
              <p className="muted small">
                {selected.created_at} · actor {selected.actor || 'system'} · agent {selected.agent || 'unspecified'}
                {selected.tags.length ? ` · tags ${selected.tags.join(', ')}` : ''}
              </p>
              <div className="bounded-preview">
                <pre>{selected.markdown}</pre>
              </div>
            </>
          ) : (
            <p className="muted">왼쪽 목록에서 패치 기록을 선택하세요.</p>
          )}
        </div>
      </div>
    </section>
  );
}
