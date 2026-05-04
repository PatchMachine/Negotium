import { useState } from 'react';

import { compressContext, refreshVolatileMemory } from '../../api';

type Props = {
  query: string;
  selectedSourceIds: string[];
  fallbackSourceIds: string[];
  onMessage: (msg: string) => void;
  onAfterCompress: () => void | Promise<void>;
};

const SUMMARY_LENGTHS = [
  { label: '짧게', value: 2000 },
  { label: '보통', value: 4000 },
  { label: '자세히', value: 8000 },
];

export default function ContextCompressPanel({
  query,
  selectedSourceIds,
  fallbackSourceIds,
  onMessage,
  onAfterCompress,
}: Props) {
  const [tokenBudget, setTokenBudget] = useState(4000);
  const [sourceLimit, setSourceLimit] = useState(20);
  const [includeVolatile, setIncludeVolatile] = useState(false);
  const [busy, setBusy] = useState(false);

  async function runCompress() {
    setBusy(true);
    try {
      const sourceIds = selectedSourceIds.length > 0 ? selectedSourceIds : fallbackSourceIds;
      await compressContext({
        scope: 'global',
        key: 'default',
        query,
        token_budget: tokenBudget,
        source_limit: sourceLimit,
        source_ids: sourceIds.length > 0 ? sourceIds.slice(0, sourceLimit) : undefined,
        include_volatile: includeVolatile,
      });
      onMessage('AI 가독 정보 요약을 생성했습니다.');
      await onAfterCompress();
    } catch (e) {
      onMessage(e instanceof Error ? e.message : 'AI 가독 정보 요약 생성 실패');
    } finally {
      setBusy(false);
    }
  }

  async function runVolatileRefresh() {
    setBusy(true);
    try {
      const sourceIds = selectedSourceIds.length > 0 ? selectedSourceIds : fallbackSourceIds;
      await refreshVolatileMemory({
        scope: 'global',
        key: 'default',
        query,
        source_limit: sourceLimit,
        source_ids: sourceIds.length > 0 ? sourceIds.slice(0, sourceLimit) : undefined,
      });
      onMessage('휘발성 메모리를 갱신했습니다.');
      await onAfterCompress();
    } catch (e) {
      onMessage(e instanceof Error ? e.message : '갱신 실패');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel memory-compress-panel">
      <p className="eyebrow">AI readable summary</p>
      <h2>AI 가독 정보 요약</h2>
      <p className="muted small">
        AI가 작업해야 하는 중요한 기억을 가져와 읽기 좋게 요약합니다. 체크한 항목이 있으면 그 항목을 우선 사용하고,
        선택이 없으면 현재 조회 종류의 기억을 가져옵니다.
      </p>
      <div className="memory-form row-compact">
        <label>
          요약 길이
          <select
            value={tokenBudget}
            onChange={(e) => setTokenBudget(Number(e.target.value))}
          >
            {SUMMARY_LENGTHS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          가져올 기억 수
          <input
            type="number"
            min={1}
            max={50}
            value={sourceLimit}
            onChange={(e) => setSourceLimit(Number(e.target.value) || 20)}
          />
        </label>
      </div>
      <label className="checkbox-inline">
        <input type="checkbox" checked={includeVolatile} onChange={(e) => setIncludeVolatile(e.target.checked)} />
        휘발성 작업 메모리도 함께 참고
      </label>
      <div className="form-actions">
        <button type="button" disabled={busy} onClick={() => void runVolatileRefresh()}>
          휘발성 메모리 갱신
        </button>
        <button type="button" className="secondary-button" disabled={busy} onClick={() => void runCompress()}>
          AI 가독 정보 요약 만들기
        </button>
      </div>
    </div>
  );
}
