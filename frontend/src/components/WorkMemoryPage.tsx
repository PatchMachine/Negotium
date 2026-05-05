import { useCallback, useEffect, useRef, useState } from 'react';

import {
  fetchConversations,
  fetchDeletionRequests,
  fetchMemorySchema,
  fetchOperationsMemory,
  fetchPermanentMemory,
  fetchVolatileMemories,
  fetchWorkMemory,
  requestMemoryDeletion,
  saveOperationsMemory,
  saveWorkMemory,
  type ConversationRecord,
  type DeletionRequest,
  type OperationsMemory,
  type PermanentMemorySource,
  type ReadableContextBundle,
  type VolatileMemory,
  type WorkMemory,
} from '../api';
import ContextCompressPanel from './memory/ContextCompressPanel';
import ConversationHistoryModal from './memory/ConversationHistoryModal';
import MemoryGovernancePanel from './memory/MemoryGovernancePanel';
import PermanentSourcesList, { type MemoryKindFilter } from './memory/PermanentSourcesList';
import ReadableContextWorkbench from './memory/ReadableContextWorkbench';
import VolatileMemoriesPanel from './memory/VolatileMemoriesPanel';
import WorkMemoryEditSection from './memory/WorkMemoryEditSection';

const emptyOperations: OperationsMemory = {
  company_name: '',
  office_project: '',
  active_plan: '',
  organization: '',
  departments: '',
  roles: '',
  key_workflows: '',
  office_tools: '',
  sensitive_policy: '',
};

const emptyWork: WorkMemory = {
  goals: '',
  active_projects: '',
  current_focus: '',
  blockers: '',
  decisions: '',
  risks: '',
  next_actions: '',
  updated_at: '',
};

export default function WorkMemoryPage() {
  const [section, setSection] = useState<'edit' | 'lookup' | 'summary' | 'cache'>('edit');
  const [editMode, setEditMode] = useState<'permanent' | 'volatile'>('permanent');
  const [operations, setOperations] = useState<OperationsMemory>(emptyOperations);
  const [work, setWork] = useState<WorkMemory>(emptyWork);
  const [sources, setSources] = useState<PermanentMemorySource[]>([]);
  const [volatileMemories, setVolatileMemories] = useState<VolatileMemory[]>([]);
  const [conversations, setConversations] = useState<ConversationRecord[]>([]);
  const [schemas, setSchemas] = useState<Array<Record<string, unknown>>>([]);
  const [schemaProposals, setSchemaProposals] = useState<Array<Record<string, unknown>>>([]);
  const [deletionRequests, setDeletionRequests] = useState<DeletionRequest[]>([]);
  const [query, setQuery] = useState('');
  const [message, setMessage] = useState('');
  const [convOpen, setConvOpen] = useState(false);
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);
  const [selectedKind, setSelectedKind] = useState<MemoryKindFilter>('all');
  const [readableBundle, setReadableBundle] = useState<ReadableContextBundle | null>(null);
  const queryRef = useRef(query);
  queryRef.current = query;

  const refreshAdminMemory = useCallback(async () => {
    const q = queryRef.current;
    const [permanent, volatilePayload, conversationPayload, schemaPayload, deletions] = await Promise.all([
      fetchPermanentMemory(q),
      fetchVolatileMemories(),
      fetchConversations(),
      fetchMemorySchema(),
      fetchDeletionRequests(),
    ]);
    setSources(permanent.sources);
    setVolatileMemories(volatilePayload.memories);
    setConversations(conversationPayload.records);
    setSchemas(schemaPayload.schemas);
    setSchemaProposals(schemaPayload.proposals);
    setDeletionRequests(deletions.requests);
  }, []);

  useEffect(() => {
    Promise.all([fetchOperationsMemory(), fetchWorkMemory(), refreshAdminMemory()])
      .then(([nextOperations, nextWork]) => {
        setOperations(nextOperations);
        setWork(nextWork);
      })
      .catch((err) => setMessage(err instanceof Error ? err.message : '메모리 로드 실패'));
  }, [refreshAdminMemory]);

  async function saveAll() {
    const [savedOperations, savedWork] = await Promise.all([saveOperationsMemory(operations), saveWorkMemory(work)]);
    setOperations(savedOperations);
    setWork(savedWork);
    setMessage('메모리를 저장했습니다.');
  }

  function toggleSource(id: string, checked: boolean) {
    setSelectedSourceIds((prev) => {
      if (checked) {
        if (prev.includes(id)) return prev;
        return [...prev, id];
      }
      return prev.filter((x) => x !== id);
    });
  }

  const filteredSources = selectedKind === 'all' ? sources : sources.filter((source) => source.kind === selectedKind);
  const currentKindSourceIds = filteredSources.map((source) => source.id);
  const sectionItems: Array<{ id: typeof section; label: string }> = [
    { id: 'edit', label: '메모리 수정' },
    { id: 'lookup', label: '패치머신 영구메모리 조회' },
    { id: 'summary', label: 'AI 가독 정보 요약' },
    { id: 'cache', label: '캐시·스키마' },
  ];

  return (
    <section className="work-memory-layout">
      <div className="work-memory-toolbar">
        <div className="segmented-control memory-section-tabs" role="tablist" aria-label="패치머신 메모리 관리 메뉴">
          {sectionItems.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={section === item.id}
              className={section === item.id ? 'segment active' : 'segment'}
              onClick={() => setSection(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <button type="button" className="secondary-button" onClick={() => void setConvOpen(true)}>
          대화 기록 열기
        </button>
      </div>

      <div className="page-grid work-memory-grid">
        {section === 'edit' ? (
          <WorkMemoryEditSection
            mode={editMode}
            onModeChange={setEditMode}
            operations={operations}
            setOperations={setOperations}
            work={work}
            setWork={setWork}
            onSave={() => void saveAll()}
            message={message}
          />
        ) : null}

        {section === 'lookup' ? (
          <PermanentSourcesList
            sources={sources}
            selectedKind={selectedKind}
            onKindChange={setSelectedKind}
            query={query}
            setQuery={setQuery}
            onRefresh={() => void refreshAdminMemory()}
            selectedIds={selectedSourceIds}
            onToggleSource={toggleSource}
            onReorderSelected={setSelectedSourceIds}
            onRequestDeletion={(source) =>
              void requestMemoryDeletion({
                target_type: source.kind,
                target_id: source.id,
                summary: source.title,
                source_path: source.path,
                sensitivity: 'internal',
                reason: '관리자 요청',
              }).then(() => refreshAdminMemory())
            }
          />
        ) : null}

        {section === 'summary' ? (
          <>
            <ReadableContextWorkbench
              query={query}
              onQueryChange={setQuery}
              selectedIds={selectedSourceIds}
              onSelectedIdsChange={setSelectedSourceIds}
              onBundlePreview={setReadableBundle}
              onRequestDeletion={(source) =>
                void requestMemoryDeletion({
                  target_type: source.kind,
                  target_id: source.id,
                  summary: source.title,
                  source_path: source.path,
                  sensitivity: source.sensitivity || 'internal',
                  reason: '관리자 요청',
                }).then(() => refreshAdminMemory())
              }
            />
            <ContextCompressPanel
              query={query}
              selectedSourceIds={selectedSourceIds}
              fallbackSourceIds={currentKindSourceIds}
              readableBundle={readableBundle}
              onMessage={setMessage}
              onAfterCompress={() => refreshAdminMemory()}
            />
          </>
        ) : null}

        {section === 'cache' ? (
          <>
            <VolatileMemoriesPanel memories={volatileMemories} onAfterChange={() => void refreshAdminMemory()} />
            <MemoryGovernancePanel
              schemas={schemas}
              schemaProposals={schemaProposals}
              deletionRequests={deletionRequests}
              onRefresh={() => void refreshAdminMemory()}
            />
          </>
        ) : null}
      </div>

      <ConversationHistoryModal open={convOpen} records={conversations} onClose={() => setConvOpen(false)} />
    </section>
  );
}
