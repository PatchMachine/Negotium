import {
  approveDeletionRequest,
  approveMemorySchemaProposal,
  proposeMemorySchema,
  rejectDeletionRequest,
  type DeletionRequest,
} from '../../api';

type Props = {
  schemas: Array<Record<string, unknown>>;
  schemaProposals: Array<Record<string, unknown>>;
  deletionRequests: DeletionRequest[];
  onRefresh: () => void | Promise<void>;
};

export default function MemoryGovernancePanel({ schemas, schemaProposals, deletionRequests, onRefresh }: Props) {
  return (
    <div className="panel memory-governance-panel">
      <p className="eyebrow">Governance</p>
      <h2>메모리 스키마 · 삭제 승인</h2>

      <details className="governance-details" open>
        <summary>스키마 및 제안</summary>
        <div className="memory-form">
          <button
            type="button"
            onClick={() =>
              void proposeMemorySchema({
                type_id: `custom_${Date.now()}`,
                display_name: '새 메모리 종류 제안',
                fields: [{ name: 'summary', type: 'text' }],
              }).then(() => onRefresh())
            }
          >
            LLM/관리자 스키마 제안 샘플
          </button>
        </div>
        <div className="log-list">
          {schemas.map((schema) => (
            <article className="log-card" key={String(schema.type_id)}>
              <strong>{String(schema.display_name)}</strong>
              <p>
                {String(schema.type_id)} · {String(schema.sensitivity)}
              </p>
            </article>
          ))}
          {schemaProposals
            .filter((proposal) => proposal.status === 'pending')
            .map((proposal) => (
              <article className="log-card" key={String(proposal.id)}>
                <strong>스키마 제안</strong>
                <p>
                  {String(proposal.mode)} · {String(proposal.id)}
                </p>
                <button type="button" onClick={() => void approveMemorySchemaProposal(String(proposal.id)).then(() => onRefresh())}>
                  승인
                </button>
              </article>
            ))}
        </div>
      </details>

      <details className="governance-details">
        <summary>삭제 요청</summary>
        <div className="log-list">
          {deletionRequests.map((request) => (
            <article className="log-card" key={request.id}>
              <strong>{request.summary}</strong>
              <p>
                {request.status} · {request.target_type} · {request.source_path}
              </p>
              {request.status === 'pending' ? (
                <>
                  <button type="button" onClick={() => void approveDeletionRequest(request.id).then(() => onRefresh())}>
                    삭제 승인
                  </button>
                  <button className="secondary-button" type="button" onClick={() => void rejectDeletionRequest(request.id).then(() => onRefresh())}>
                    거절
                  </button>
                </>
              ) : null}
            </article>
          ))}
        </div>
      </details>
    </div>
  );
}
