import {
  approveAgentPlan,
  generateAgentPlan,
  runAgentPlan,
  type AgentPlan,
} from '../../api';

type Props = {
  plans: AgentPlan[];
  agentObjective: string;
  setAgentObjective: (v: string) => void;
  onMessage: (msg: string) => void;
  onRefresh: () => void | Promise<void>;
};

export default function AgentPlansPanel({ plans, agentObjective, setAgentObjective, onMessage, onRefresh }: Props) {
  return (
    <section className="panel agent-plans-section" aria-labelledby="agent-plans-heading">
      <p className="eyebrow">Agent execution</p>
      <h2 id="agent-plans-heading">에이전트 실행 계획</h2>
      <p className="muted small">계획 생성 후 승인·실행 요청을 분리된 목록에서 처리합니다.</p>
      <div className="memory-form">
        <input
          placeholder="에이전트 작업 목표"
          value={agentObjective}
          onChange={(e) => setAgentObjective(e.target.value)}
        />
        <button
          type="button"
          onClick={() =>
            void generateAgentPlan({
              objective: agentObjective,
              title: agentObjective,
              mode: 'approved_tasks_only',
              schedule_refs: [],
              memory_refs: [],
            }).then(() => onRefresh())
          }
        >
          계획 생성
        </button>
      </div>
      <ul className="agent-plan-list" aria-label="에이전트 계획 목록">
        {plans.map((plan) => (
          <li key={plan.id} className="agent-plan-card">
            <div className="agent-plan-head">
              <strong>{plan.title}</strong>
              <span className="muted small">
                {plan.status} · {plan.mode} · 단계 {plan.steps.length}
              </span>
            </div>
            <div className="form-actions">
              <button type="button" onClick={() => void approveAgentPlan(plan.id).then(() => onRefresh())}>
                승인
              </button>
              <button
                className="secondary-button"
                type="button"
                onClick={() =>
                  void runAgentPlan(plan.id).then(() => {
                    onMessage('실행 요청을 기록했습니다.');
                  })
                }
              >
                실행 요청
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
