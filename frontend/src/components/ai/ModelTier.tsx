import type { ModelProfile, ModelTier, ProviderModelPayload } from '../../api';

/**
 * Shared tier presentation for every place a user picks a model
 * (setup wizard, admin settings, task routing).
 *
 * Tier data comes from the backend catalog (`adapters/llm/catalog.py`) so the
 * classification and the "what stops working" guidance live in one place
 * instead of being duplicated per screen.
 */

export const TIER_ORDER: ModelTier[] = ['agent', 'reasoning', 'general', 'unknown'];

export const TIER_FALLBACK_LABELS: Record<ModelTier, string> = {
  agent: '에이전트형',
  reasoning: '추론형',
  general: '일반형',
  unknown: '미분류',
};

export const TIER_SUMMARIES: Record<ModelTier, string> = {
  agent: '도구를 스스로 호출해 여러 단계 업무를 수행합니다.',
  reasoning: '분석·문서 작업에 강하고 도구도 사용할 수 있습니다.',
  general: '빠른 대화와 요약에 적합합니다.',
  unknown: '카탈로그에 없는 모델이라 기능을 보장할 수 없습니다.',
};

export function profileMap(payload: ProviderModelPayload | null): Map<string, ModelProfile> {
  const entries = new Map<string, ModelProfile>();
  for (const profile of payload?.model_profiles || []) {
    entries.set(profile.id, profile);
  }
  return entries;
}

export function tierOf(profile: ModelProfile | undefined): ModelTier {
  return profile?.tier || 'unknown';
}

/** Group model ids by tier, preserving the incoming order within each tier. */
export function groupByTier(
  models: string[],
  profiles: Map<string, ModelProfile>,
): { tier: ModelTier; label: string; models: string[] }[] {
  const grouped = new Map<ModelTier, string[]>();
  for (const model of models) {
    const tier = tierOf(profiles.get(model));
    grouped.set(tier, [...(grouped.get(tier) || []), model]);
  }
  return TIER_ORDER.filter((tier) => (grouped.get(tier) || []).length > 0).map((tier) => ({
    tier,
    label: TIER_FALLBACK_LABELS[tier],
    models: grouped.get(tier) || [],
  }));
}

export function TierBadge({ tier, label }: { tier: ModelTier; label?: string }) {
  return (
    <span className={`tier-badge tier-badge-${tier}`} title={TIER_SUMMARIES[tier]}>
      {label || TIER_FALLBACK_LABELS[tier]}
    </span>
  );
}

/**
 * Tells the user which product features the selected model turns off.
 *
 * This is the "로컬 LLM 설정 시 어떤 기능이 제한되는지" guidance: a local
 * general-tier model cannot drive tool-based chat, so the wizard must say so
 * before the user commits rather than leaving them to discover dead features.
 */
export function ModelCapabilityNotice({
  profile,
  suggestion,
}: {
  profile: ModelProfile | undefined;
  suggestion?: string;
}) {
  if (!profile) return null;
  const restricted = profile.restricted || [];
  if (!restricted.length) {
    return (
      <p className="hint model-capability-ok">
        <TierBadge tier={profile.tier} label={profile.tier_label} /> 이 모델은 네고티움의 모든 기능을
        사용할 수 있습니다.
      </p>
    );
  }
  return (
    <div className="notice model-capability-warning">
      <p>
        <TierBadge tier={profile.tier} label={profile.tier_label} />{' '}
        {profile.source === 'inferred'
          ? '카탈로그에 없는 모델이라 기능을 보수적으로 판단했습니다.'
          : TIER_SUMMARIES[profile.tier]}
      </p>
      <p>이 모델을 선택하면 다음 기능이 제한됩니다:</p>
      <ul>
        {restricted.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
      {suggestion ? <p className="hint">{suggestion}</p> : null}
    </div>
  );
}

/** Standing recommendation shown when the chosen model cannot use tools. */
export const TOOL_FALLBACK_SUGGESTION =
  '권장: 도구 사용이 필요하면 solar-pro3(에이전트형) 또는 solar-pro2(추론형)를 클라우드 라우트로 함께 설정하세요. 민감 업무만 로컬로 라우팅하면 두 이점을 모두 얻을 수 있습니다.';

/** `<select>` children that group options by tier. */
export function TieredModelOptions({
  models,
  profiles,
}: {
  models: string[];
  profiles: Map<string, ModelProfile>;
}) {
  const groups = groupByTier(models, profiles);
  return (
    <>
      {groups.map((group) => (
        <optgroup key={group.tier} label={group.label}>
          {group.models.map((model) => {
            const profile = profiles.get(model);
            return (
              <option key={model} value={model}>
                {profile?.label ? `${model} — ${profile.label}` : model}
              </option>
            );
          })}
        </optgroup>
      ))}
    </>
  );
}
