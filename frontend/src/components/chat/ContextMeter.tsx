import type { ContextUsage } from '../../api';

/**
 * How much of the model's context window this conversation is using.
 *
 * Without it "why did the assistant forget what I said?" is unanswerable from
 * the UI — memory blocks, replayed turns and tool results all compete for the
 * same window and none of it was visible.
 */

const WARN_RATIO = 0.75;
const DANGER_RATIO = 0.9;

function formatTokens(value: number): string {
  if (value >= 1000) return `${(value / 1000).toFixed(value >= 10_000 ? 0 : 1)}k`;
  return String(value);
}

export default function ContextMeter({ usage }: { usage: ContextUsage | null }) {
  if (!usage || !usage.context_window) return null;

  const ratio = Math.min(1, Math.max(0, usage.used_ratio));
  const percent = Math.round(ratio * 100);
  const level = ratio >= DANGER_RATIO ? 'danger' : ratio >= WARN_RATIO ? 'warn' : 'ok';
  const used = usage.prompt_tokens + usage.completion_tokens;

  return (
    <div className={`context-meter context-meter-${level}`}>
      <div className="context-meter-head">
        <span>컨텍스트 {percent}%</span>
        <span className="muted small">
          {formatTokens(used)} / {formatTokens(usage.context_window)} 토큰
          {usage.estimated ? ' (추정)' : ''}
        </span>
      </div>
      <div
        className="context-meter-track"
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="컨텍스트 사용량"
      >
        <div className="context-meter-fill" style={{ width: `${percent}%` }} />
      </div>
      <p className="muted small context-meter-detail">
        대화 {usage.history_turns}턴 재생
        {usage.tool_result_tokens > 0
          ? ` · 도구 결과 ${formatTokens(usage.tool_result_tokens)} 토큰`
          : ''}
      </p>
      {level !== 'ok' ? (
        <p className="muted small">
          {level === 'danger'
            ? '창이 거의 찼습니다. 새 대화를 시작하면 이전 맥락 없이 깨끗하게 이어갈 수 있습니다.'
            : '창이 채워지고 있습니다. 주제가 바뀌면 새 대화를 시작하는 편이 좋습니다.'}
        </p>
      ) : null}
    </div>
  );
}
