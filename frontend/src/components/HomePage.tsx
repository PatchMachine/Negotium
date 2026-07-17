import type { ApiStatus, OperationsMemory } from '../api';

const dailyFlow = [
  {
    step: '1',
    eyebrow: '회의록 → 업무 배정',
    title: '회의 메모를 붙여넣으면 업무가 배정됩니다',
    description:
      '문서 자동화에서 회의록을 생성하면 AI가 액션 아이템을 뽑아 담당자별 업무 순서까지 등록합니다.',
    page: 'documents',
    action: '회의록 만들기',
  },
  {
    step: '2',
    eyebrow: '업무 현황 · 주간보고',
    title: '쌓인 업무 기록이 보고서가 됩니다',
    description:
      '업무 현황에서 진행/완료/병목을 확인하고, 버튼 한 번으로 관리자용 주간 업무 보고서를 생성합니다.',
    page: 'work',
    action: '업무 현황 · 주간보고',
  },
  {
    step: '3',
    eyebrow: '인수인계',
    title: '담당자가 바뀌어도 업무는 이어집니다',
    description:
      '떠나는 담당자의 업무 기록·감사 로그를 모아 인수인계 문서를 만들고, 후속 업무를 새 담당자에게 자동 배정합니다.',
    page: 'handover',
    action: '인수인계 킷 생성',
  },
  {
    step: '4',
    eyebrow: '채용 · 면접',
    title: '빈 자리는 채용 키트로 채웁니다',
    description:
      '부서/직급 컨텍스트를 반영해 직무 요구사항, 면접 질문, 온보딩 계획을 한 번에 생성합니다.',
    page: 'hiring',
    action: '채용 키트 만들기',
  },
];

export default function HomePage({
  memory,
  status,
  onAction,
}: {
  memory: OperationsMemory;
  status: ApiStatus | null;
  onAction: (page: string) => void;
}) {
  const memoryState = status?.operations_memory_configured ? '설정 완료' : '초기 상태';
  return (
    <section>
      <div className="hero-panel">
        <p className="eyebrow">AI Office BPA Console</p>
        <h1>회의록부터 주간보고까지, 오피스워크가 스스로 굴러갑니다</h1>
        <p className="lede">
          {memory.company_name ? `${memory.company_name}의 ` : ''}
          회의 기록이 업무 배정이 되고, 업무 기록이 보고서·인수인계·채용 키트가 됩니다. 민감한 내용은
          로컬 LLM으로, 일반 업무는 Upstage Solar로 처리합니다.
        </p>
      </div>

      <section className="guide-grid">
        {dailyFlow.map((flow) => (
          <article className="guide-card" key={flow.page}>
            <p className="eyebrow">
              {flow.step}. {flow.eyebrow}
            </p>
            <h3>{flow.title}</h3>
            <p>{flow.description}</p>
            <button type="button" onClick={() => onAction(flow.page)}>
              {flow.action}
            </button>
          </article>
        ))}
      </section>

      <section className="guide-grid">
        <article className="guide-card">
          <p className="eyebrow">회사 메모리</p>
          <h3>{memory.company_name || '회사 미설정'}</h3>
          <p>
            {memory.office_project ||
              '회사·조직·업무 흐름을 등록하면 모든 문서와 배정에 회사 맥락이 반영됩니다.'}
          </p>
          <button type="button" onClick={() => onAction('dashboard')}>운영 메모리 설정</button>
        </article>
        <article className="guide-card">
          <p className="eyebrow">시스템 상태</p>
          <h3>API {status?.ok ? '정상' : '확인 중'} · 메모리 {memoryState}</h3>
          <p>AI 어시스턴트에게 현재 업무 맥락을 바로 물어볼 수 있습니다.</p>
          <button type="button" onClick={() => onAction('assistant')}>AI 어시스턴트 열기</button>
        </article>
        <article className="guide-card">
          <p className="eyebrow">관리</p>
          <h3>API 키 · 권한 · 업로드</h3>
          <p>Solar API 키 등록, 직급/권한, 문서 업로드를 관리자 페이지에서 처리합니다.</p>
          <button type="button" onClick={() => onAction('admin')}>관리 페이지 열기</button>
        </article>
      </section>
    </section>
  );
}
