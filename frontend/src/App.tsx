import { useEffect, useState } from 'react';

import { fetchApiStatus, fetchOperationsMemory, type ApiStatus, type OperationsMemory } from './api';
import AccessControlPage from './components/AccessControlPage';
import AdminSettingsPage from './components/AdminSettingsPage';
import AppShell from './components/AppShell';
import ContributorGuide from './components/ContributorGuide';
import DocumentAutomationPage from './components/DocumentAutomationPage';
import HandoverPage from './components/HandoverPage';
import HiringPage from './components/HiringPage';
import HomePage from './components/HomePage';
import IntegrationsPage from './components/IntegrationsPage';
import LlmChatPage from './components/LlmChatPage';
import OperationsMemoryForm from './components/OperationsMemoryForm';
import ProgressLogPage from './components/ProgressLogPage';
import SystemStatus from './components/SystemStatus';
import UploadPage from './components/UploadPage';
import WorkItemsPage from './components/WorkItemsPage';

const emptyMemory: OperationsMemory = {
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

type Page =
  | 'home'
  | 'dashboard'
  | 'chat'
  | 'progress'
  | 'work'
  | 'hiring'
  | 'documents'
  | 'handover'
  | 'integrations'
  | 'uploads'
  | 'admin'
  | 'access';

const navItems: Array<{ id: Page; label: string; group: string }> = [
  { id: 'home', label: '홈', group: '사이트' },
  { id: 'dashboard', label: '운영 메모리', group: '운영' },
  { id: 'work', label: '업무 현황', group: '운영' },
  { id: 'progress', label: '진행 로그', group: '운영' },
  { id: 'chat', label: 'LLM 채팅', group: 'AI' },
  { id: 'hiring', label: '채용/면접', group: '오피스워크' },
  { id: 'documents', label: '문서 자동화', group: '오피스워크' },
  { id: 'handover', label: '인수인계', group: '오피스워크' },
  { id: 'integrations', label: 'GitHub/Discord', group: '연동' },
  { id: 'uploads', label: '업로드', group: '관리' },
  { id: 'admin', label: 'API 설정', group: '관리' },
  { id: 'access', label: '권한 관리', group: '관리' },
];

export default function App() {
  const [memory, setMemory] = useState<OperationsMemory>(emptyMemory);
  const [status, setStatus] = useState<ApiStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState<Page>('home');

  async function refresh() {
    setError(null);
    try {
      const [nextMemory, nextStatus] = await Promise.all([
        fetchOperationsMemory(),
        fetchApiStatus(),
      ]);
      setMemory(nextMemory);
      setStatus(nextStatus);
    } catch (err) {
      setError(err instanceof Error ? err.message : '알 수 없는 오류가 발생했습니다.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  return (
    <AppShell page={page} navItems={navItems} onNavigate={setPage}>
      {error ? <div className="alert">API 연결 실패: {error}</div> : null}

      {page === 'home' ? <HomePage memory={memory} status={status} onAction={(next) => setPage(next as Page)} /> : null}

      {page === 'dashboard' ? (
        <>
          <section className="dashboard-grid">
            <OperationsMemoryForm
              disabled={loading}
              memory={memory}
              onSaved={(nextMemory) => {
                setMemory(nextMemory);
                void refresh();
              }}
            />
            <SystemStatus loading={loading} status={status} onRefresh={() => void refresh()} />
          </section>
          <ContributorGuide />
        </>
      ) : null}
      {page === 'chat' ? <LlmChatPage /> : null}
      {page === 'progress' ? <ProgressLogPage /> : null}
      {page === 'work' ? <WorkItemsPage /> : null}
      {page === 'hiring' ? <HiringPage /> : null}
      {page === 'documents' ? <DocumentAutomationPage /> : null}
      {page === 'handover' ? <HandoverPage /> : null}
      {page === 'integrations' ? <IntegrationsPage /> : null}
      {page === 'uploads' ? <UploadPage /> : null}
      {page === 'admin' ? <AdminSettingsPage /> : null}
      {page === 'access' ? <AccessControlPage /> : null}
    </AppShell>
  );
}
