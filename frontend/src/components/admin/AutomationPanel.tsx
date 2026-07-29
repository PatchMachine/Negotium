import { useEffect, useState } from 'react';

import {
  fetchAutomationStatus,
  runAutomationJobs,
  saveAutomationConfig,
  type AutomationConfig,
} from '../../api';

const WEEKDAY_LABELS = ['월', '화', '수', '목', '금', '토', '일'];

const emptyConfig: AutomationConfig = {
  weekly_report: { enabled: false, weekday: 0, time: '09:00', timezone: 'Asia/Seoul' },
  reminders: { enabled: false, time: '09:30', stale_days: 3 },
  webhook_url: '',
};

export default function AutomationPanel() {
  const [config, setConfig] = useState<AutomationConfig>(emptyConfig);
  const [state, setState] = useState<Record<string, string>>({});
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
