import { FormEvent, useEffect, useState } from 'react';

import {
  analyzePatchRun,
  approvePatchRunPlan,
  createPatchRun,
  draftPatchRunDiff,
  fetchPatchRun,
  fetchPatchRuns,
  writePatchRunMemory,
  type IssueCluster,
  type PatchEvent,
  type PatchRun,
  type TestRequirement,
} from '../../api';
import AiTestWriterPanel from './AiTestWriterPanel';
import IssueMemoryPanel from './IssueMemoryPanel';

type Props = {
  onMessage: (message: string) => void;
};

export default function PatchOpsCockpit({ onMessage }: Props) {
  const [runs, setRuns] = useState<PatchRun[]>([]);
  const [selected, setSelected] = useState<PatchRun | null>(null);
  const [events, setEvents] = useState<PatchEvent[]>([]);
  const [repoId, setRepoId] = useState('local');
  const [request, setRequest] = useState('');
  const [autonomyLevel, setAutonomyLevel] = useState('L1');
  const [privacyMode, setPrivacyMode] = useState('hybrid_redacted');
  const [busy, setBusy] = useState(false);

  async function refreshRuns() {
    const payload = await fetchPatchRuns();
    setRuns(payload.patch_runs);
    if (!selected && payload.patch_runs[0]) {
      await loadRun(payload.patch_runs[0].id);
    }
  }

  async function loadRun(id: string) {
    const payload = await fetchPatchRun(id);
    setSelected(payload.patch_run);
    setEvents(payload.events);
  }

  useEffect(() => {
    void refreshRuns().catch((err) => onMessage(err instanceof Error ? err.message : 'PatchOps 로드 실패'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function createRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!request.trim()) return;
    setBusy(true);
    try {
      const payload = await createPatchRun({
        repo_id: repoId,
        request,
        autonomy_level: autonomyLevel,
        privacy_mode: privacyMode,
        target_branch: 'main',
        constraints: {
          no_new_dependencies: true,
          require_tests: true,
          require_human_approval_for_auth: true,
        },
      });
      setRequest('');
      await refreshRuns();
      await loadRun(payload.patch_run.id);
    } catch (err) {
      onMessage(err instanceof Error ? err.message : 'PatchOps run 생성 실패');
    } finally {
      setBusy(false);
    }
  }

  async function runStep(action: 'analyze' | 'approve' | 'draft' | 'memory') {
    if (!selected) return;
    setBusy(true);
    try {
      if (action === 'analyze') {
        const payload = await analyzePatchRun(selected.id);
        setSelected(payload.patch_run);
        setEvents(payload.events);
      } else if (action === 'approve') {
        const payload = await approvePatchRunPlan(selected.id);
        setSelected(payload.patch_run);
        await loadRun(selected.id);
      } else if (action === 'draft') {
        const payload = await draftPatchRunDiff(selected.id);
        setSelected(payload.patch_run);
        setEvents(payload.events);
      } else {
        const payload = await writePatchRunMemory(selected.id);
        setSelected(payload.patch_run);
        await loadRun(selected.id);
      }
      await refreshRuns();
    } catch (err) {
      onMessage(err instanceof Error ? err.message : 'PatchOps 단계 실행 실패');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel agent-plans-section" aria-labelledby="patchops-heading">
      <p className="eyebrow">PatchOps Agent</p>
      <h2 id="patchops-heading">자가코딩 패치 운영</h2>
      <p className="muted small">코드 조사, 자가 질문, 패치 계획, diff 초안, PR/패치노트, 영구 메모리를 안전한 승인 루프로 생성합니다.</p>

      <form className="memory-form" onSubmit={createRun}>
        <input value={repoId} onChange={(event) => setRepoId(event.target.value)} placeholder="repo id (local 또는 owner/repo)" />
        <textarea value={request} onChange={(event) => setRequest(event.target.value)} placeholder="예: 로그인 후 세션이 끊기는 문제를 조사하고 패치 계획을 만들어줘" />
        <div className="form-grid">
          <label>
            Autonomy
            <select value={autonomyLevel} onChange={(event) => setAutonomyLevel(event.target.value)}>
              <option value="L0">L0 Read Only</option>
              <option value="L1">L1 Draft Patch</option>
              <option value="L2">L2 Branch Patch</option>
              <option value="L3">L3 PR Automation</option>
            </select>
          </label>
          <label>
            Privacy
            <select value={privacyMode} onChange={(event) => setPrivacyMode(event.target.value)}>
              <option value="local_only">Local Only</option>
              <option value="hybrid_redacted">Hybrid Redacted</option>
              <option value="frontier_assisted">Frontier Assisted</option>
            </select>
          </label>
        </div>
        <button type="submit" disabled={busy}>{busy ? '처리 중...' : 'Patch Run 생성'}</button>
      </form>

      <div className="split-panel">
        <div>
          <h3>Patch Runs</h3>
          <ul className="agent-plan-list">
            {runs.map((run) => (
              <li key={run.id} className="agent-plan-card">
                <button className="link-button" type="button" onClick={() => void loadRun(run.id)}>
                  <strong>{run.request}</strong>
                  <span className="muted small">{run.status} · risk {run.risk_level} · {run.privacy_mode}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>

        {selected ? (
          <div>
            <div className="agent-plan-head">
              <strong>{selected.request}</strong>
              <span className="status-pill">{selected.status}</span>
            </div>
            <div className="form-actions">
              <button type="button" disabled={busy} onClick={() => void runStep('analyze')}>분석</button>
              <button type="button" disabled={busy} onClick={() => void runStep('approve')}>계획 승인</button>
              <button type="button" disabled={busy} onClick={() => void runStep('draft')}>Diff/문서 초안</button>
              <button type="button" disabled={busy} onClick={() => void runStep('memory')}>영구 메모리 저장</button>
            </div>
            <PatchLiveBriefingPanel events={events} />
            <IssueMemoryPanel clusters={arrayFromContext<IssueCluster>(selected.context.issue_clusters)} onMessage={onMessage} />
            <PatchInterviewPanel questions={selected.questions} />
            <PatchPlanPanel plan={selected.plan} />
            <AiTestWriterPanel
              requirements={arrayFromArtifact<TestRequirement>(selected.artifacts.test_requirements)}
              frameworks={selected.artifacts.test_frameworks}
              patterns={selected.artifacts.test_patterns}
              testPlan={selected.artifacts.test_plan}
              testDiffDraft={selected.artifacts.test_diff_draft}
              testRunPreview={selected.artifacts.test_run_preview}
              notes={selected.artifacts.test_writer_notes}
            />
            <PatchArtifactsPanel artifacts={selected.artifacts} />
          </div>
        ) : (
          <p className="muted">Patch run을 생성하거나 선택하세요.</p>
        )}
      </div>
    </section>
  );
}

function arrayFromContext<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

function arrayFromArtifact<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

function PatchLiveBriefingPanel({ events }: { events: PatchEvent[] }) {
  return (
    <section>
      <h3>Live Briefing</h3>
      <div className="log-list">
        {events.map((event) => (
          <article className="log-card" key={event.id}>
            <strong>{event.type}</strong>
            <p>{event.summary}</p>
            <small>{event.created_at}</small>
          </article>
        ))}
      </div>
    </section>
  );
}

function PatchInterviewPanel({ questions }: { questions: Array<Record<string, unknown>> }) {
  return (
    <section>
      <h3>Patch Interview</h3>
      <div className="log-list">
        {questions.map((question, index) => (
          <article className="log-card" key={`${question.question}-${index}`}>
            <strong>{String(question.question || '질문')}</strong>
            <p>{String(question.why_it_matters || '')}</p>
            <small>{String(question.priority || 'normal')} · {question.needs_human ? '사용자 확인 필요' : '코드로 확인 가능'}</small>
          </article>
        ))}
      </div>
    </section>
  );
}

function PatchPlanPanel({ plan }: { plan: Record<string, unknown> }) {
  if (!Object.keys(plan).length) return null;
  return (
    <section>
      <h3>Patch Plan</h3>
      <pre>{JSON.stringify(plan, null, 2)}</pre>
    </section>
  );
}

function PatchArtifactsPanel({ artifacts }: { artifacts: Record<string, unknown> }) {
  if (!Object.keys(artifacts).length) return null;
  return (
    <section>
      <h3>Diff / PR / Patch Notes</h3>
      <pre>{JSON.stringify(artifacts, null, 2)}</pre>
    </section>
  );
}
