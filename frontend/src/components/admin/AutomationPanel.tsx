import { useEffect, useState } from 'react';

import {
  fetchAutomationStatus,
  fetchBackupStats,
  fetchSearchIndexStats,
  runAutomationJobs,
  saveAutomationConfig,
  type AutomationConfig,
  type BackupStats,
  type SearchIndexStats,
} from '../../api';

const WEEKDAY_LABELS = ['월', '화', '수', '목', '금', '토', '일'];

const emptyConfig: AutomationConfig = {
  weekly_report: { enabled: false, weekday: 0, time: '09:00', timezone: 'Asia/Seoul' },
  reminders: { enabled: false, time: '09:30', stale_days: 3 },
  search: { embeddings_enabled: false },
  backup: { enabled: false, interval_minutes: 30, remote_url: '' },
  webhook_url: '',
};

export default function AutomationPanel() {
  const [config, setConfig] = useState<AutomationConfig>(emptyConfig);
  const [state, setState] = useState<Record<string, string>>({});
  const [searchStats, setSearchStats] = useState<SearchIndexStats | null>(null);
  const [backupStats, setBackupStats] = useState<BackupStats | null>(null);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  async function refresh() {
    try {
      const status = await fetchAutomationStatus();
      setConfig(status.config);
      setState(status.state);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '자동화 설정 로드 실패');
    }
    try {
      setSearchStats(await fetchSearchIndexStats());
    } catch {
      setSearchStats(null);
    }
    try {
      setBackupStats(await fetchBackupStats());
    } catch {
      setBackupStats(null);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function save() {
    setBusy(true);
    setMessage('');
    try {
      const status = await saveAutomationConfig(config);
      setConfig(status.config);
      setState(status.state);
      setMessage('자동화 설정을 저장했습니다.');
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '저장 실패');
    } finally {
      setBusy(false);
    }
  }

  async function runNow(job: string) {
    setBusy(true);
    setMessage('');
    try {
      const result = await runAutomationJobs([job]);
      setMessage(
        result.executed.length
          ? `실행 완료: ${result.executed.join(', ')}`
          : '실행할 작업이 없거나 실행에 실패했습니다. 감사 로그를 확인하세요.',
      );
      await refresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '실행 실패');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel">
      <h2>자동화</h2>
      <p className="muted">
        주간보고 자동 생성과 업무 리마인더를 예약합니다. 알림은 콘솔 알림함과 웹훅으로 전달됩니다.
      </p>

      <div className="memory-form">
        <h3>주간보고 자동 생성</h3>
        <label>
          <input
            type="checkbox"
            checked={config.weekly_report.enabled}
            onChange={(e) =>
              setConfig({
                ...config,
                weekly_report: { ...config.weekly_report, enabled: e.target.checked },
              })
            }
          />
          사용
        </label>
        <label>
          요일
          <select
            value={config.weekly_report.weekday}
            onChange={(e) =>
              setConfig({
                ...config,
                weekly_report: { ...config.weekly_report, weekday: Number(e.target.value) },
              })
            }
          >
            {WEEKDAY_LABELS.map((label, index) => (
              <option key={label} value={index}>
                {label}요일
              </option>
            ))}
          </select>
        </label>
        <label>
          시각
          <input
            type="time"
            value={config.weekly_report.time}
            onChange={(e) =>
              setConfig({
                ...config,
                weekly_report: { ...config.weekly_report, time: e.target.value },
              })
            }
          />
        </label>
        <label>
          시간대
          <input
            value={config.weekly_report.timezone}
            onChange={(e) =>
              setConfig({
                ...config,
                weekly_report: { ...config.weekly_report, timezone: e.target.value },
              })
            }
          />
        </label>
        <button type="button" disabled={busy} onClick={() => void runNow('weekly_report')}>
          주간보고 지금 실행
        </button>
        {state.last_weekly_run_key ? (
          <p className="muted small">마지막 실행 주차: {state.last_weekly_run_key}</p>
        ) : null}
      </div>

      <div className="memory-form">
        <h3>업무 리마인더</h3>
        <label>
          <input
            type="checkbox"
            checked={config.reminders.enabled}
            onChange={(e) =>
              setConfig({ ...config, reminders: { ...config.reminders, enabled: e.target.checked } })
            }
          />
          사용 (마감 초과·오늘 마감·정체 업무를 담당자별로 알림)
        </label>
        <label>
          시각
          <input
            type="time"
            value={config.reminders.time}
            onChange={(e) =>
              setConfig({ ...config, reminders: { ...config.reminders, time: e.target.value } })
            }
          />
        </label>
        <label>
          정체 기준 (일)
          <input
            type="number"
            min={1}
            max={90}
            value={config.reminders.stale_days}
            onChange={(e) =>
              setConfig({
                ...config,
                reminders: { ...config.reminders, stale_days: Number(e.target.value) || 3 },
              })
            }
          />
        </label>
        <button type="button" disabled={busy} onClick={() => void runNow('reminders')}>
          리마인더 지금 실행
        </button>
        {state.last_reminder_date ? (
          <p className="muted small">마지막 리마인더 날짜: {state.last_reminder_date}</p>
        ) : null}
      </div>

      <div className="memory-form">
        <h3>아카이브 검색 (시맨틱)</h3>
        <p className="muted small">
          키워드 검색은 항상 로컬에서 동작합니다. 아래를 켜면 문서 조각을 Upstage 임베딩 API로
          보내 유의어 검색을 보강합니다 — 반출 제어(방화벽)를 통과한 조각만 전송됩니다.
        </p>
        <label>
          <input
            type="checkbox"
            checked={config.search.embeddings_enabled}
            onChange={(e) =>
              setConfig({ ...config, search: { embeddings_enabled: e.target.checked } })
            }
          />
          임베딩 시맨틱 검색 사용 (호출당 과금)
        </label>
        <button type="button" disabled={busy} onClick={() => void runNow('search_index')}>
          지금 재색인
        </button>
        {searchStats ? (
          <p className="muted small">
            파일 {searchStats.files} · 청크 {searchStats.chunks} · 임베딩 {searchStats.embedded} ·
            제외 {searchStats.embed_skipped}
            {searchStats.last_embed_run
              ? ` · 마지막 실행 ${searchStats.last_embed_run.slice(0, 16).replace('T', ' ')}`
              : ''}
          </p>
        ) : null}
      </div>

      <div className="memory-form">
        <h3>아카이브 백업 (git)</h3>
        <p className="muted small">
          archive/ 디렉터리를 자체 git 저장소로 버전 관리합니다 — 문서 변경 이력 추적과 실수
          복구가 가능해집니다. secrets와 파생 캐시는 커밋되지 않습니다.
        </p>
        <label>
          <input
            type="checkbox"
            checked={config.backup.enabled}
            onChange={(e) =>
              setConfig({ ...config, backup: { ...config.backup, enabled: e.target.checked } })
            }
          />
          자동 커밋 사용
        </label>
        <label>
          주기 (분)
          <input
            type="number"
            min={5}
            max={1440}
            value={config.backup.interval_minutes}
            onChange={(e) =>
              setConfig({
                ...config,
                backup: { ...config.backup, interval_minutes: Number(e.target.value) || 30 },
              })
            }
          />
        </label>
        <label>
          원격 저장소 URL (선택)
          <input
            placeholder="https://<token>@github.com/company/archive-backup.git"
            value={config.backup.remote_url}
            onChange={(e) =>
              setConfig({ ...config, backup: { ...config.backup, remote_url: e.target.value } })
            }
          />
        </label>
        <p className="muted small">
          원격 URL을 설정하면 커밋 후 push합니다 — 회사 데이터가 외부 저장소로 전송되며, URL에
          포함된 액세스 토큰은 로그·감사 기록에 남지 않습니다.
        </p>
        <button type="button" disabled={busy} onClick={() => void runNow('archive_backup')}>
          지금 백업
        </button>
        {backupStats?.initialized ? (
          <p className="muted small">
            커밋 {backupStats.commits}
            {backupStats.last_commit_at
              ? ` · 마지막 ${backupStats.last_commit_at.slice(0, 16).replace('T', ' ')}`
              : ''}
            {backupStats.dirty ? ' · 미커밋 변경 있음' : ''}
          </p>
        ) : null}
      </div>

      <div className="memory-form">
        <h3>웹훅</h3>
        <p className="muted small">
          {'{"text": "..."} 형식의 JSON을 POST합니다 (슬랙 incoming webhook 호환).'}
        </p>
        <input
          placeholder="https://hooks.example.com/..."
          value={config.webhook_url}
          onChange={(e) => setConfig({ ...config, webhook_url: e.target.value })}
        />
      </div>

      <button type="button" disabled={busy} onClick={() => void save()}>
        설정 저장
      </button>
      {message ? <p className="muted">{message}</p> : null}
    </section>
  );
}
