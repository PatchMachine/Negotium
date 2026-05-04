import { useEffect, useState } from 'react';

import {
  fetchApiStatus,
  fetchCurrentUser,
  fetchOperationsMemory,
  fetchSetupStatus,
  type ApiStatus,
  type AuthUser,
  type OperationsMemory,
} from './api';
import AccessControlPage from './components/AccessControlPage';
import AdminSettingsPage from './components/AdminSettingsPage';
import AppShell from './components/AppShell';
import AuthPage from './components/AuthPage';
import ContributorGuide from './components/ContributorGuide';
import DocumentAutomationPage from './components/DocumentAutomationPage';
import HandoverPage from './components/HandoverPage';
import HrEvaluationPage from './components/HrEvaluationPage';
import HiringPage from './components/HiringPage';
import HomePage from './components/HomePage';
import IntegrationsPage from './components/IntegrationsPage';
import OperationsMemoryForm from './components/OperationsMemoryForm';
import ProgressLogPage from './components/ProgressLogPage';
import SystemStatus from './components/SystemStatus';
import UploadPage from './components/UploadPage';
import UserProfilePage from './components/UserProfilePage';
import WorkArchitecturePage from './components/WorkArchitecturePage';
import WorkItemsPage from './components/WorkItemsPage';
import WorkMemoryPage from './components/WorkMemoryPage';
import WorkSchedulePage from './components/WorkSchedulePage';
import AiAgentPage from './components/ai/AiAgentPage';
import InitialOfficeSetupWizard from './components/setup/InitialOfficeSetupWizard';

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
  | 'profile'
  | 'dashboard'
  | 'chat'
  | 'progress'
  | 'work'
  | 'work-memory'
  | 'work-architecture'
  | 'work-schedule'
  | 'hiring'
  | 'documents'
  | 'handover'
  | 'integrations'
  | 'uploads'
  | 'admin'
  | 'access'
  | 'hr-evaluation';

type NavItem = { id: Page; label: string; group: string; requiredPermission?: string };

const navItems: NavItem[] = [
  { id: 'home', label: '홈', group: '사이트' },
  { id: 'profile', label: '유저 프로필', group: '사이트' },
  { id: 'dashboard', label: '회사 운영 설정', group: '회사 업무 운영' },
  { id: 'work', label: '업무 현황', group: '회사 업무 운영' },
  { id: 'work-architecture', label: '업무 아키텍처', group: '회사 업무 운영' },
  { id: 'work-schedule', label: '작업 스케줄', group: '회사 업무 운영' },
  { id: 'progress', label: '진행 로그', group: '회사 업무 운영' },
  { id: 'work-memory', label: '패치머신 메모리', group: '패치머신 메모리 관리' },
  { id: 'chat', label: 'AI 에이전트 실행계획', group: 'AI 에이전트' },
  { id: 'hiring', label: '채용/면접', group: '오피스워크' },
  { id: 'documents', label: '문서 자동화', group: '오피스워크' },
  { id: 'handover', label: '인수인계', group: '오피스워크' },
  { id: 'uploads', label: '업로드', group: '관리', requiredPermission: 'uploads:write' },
  { id: 'admin', label: 'API 키·로컬 에이전트', group: '관리', requiredPermission: 'admin:api_keys' },
  { id: 'access', label: '권한 관리', group: '관리', requiredPermission: 'admin:users' },
  { id: 'integrations', label: 'MCP 서버 연동', group: '관리', requiredPermission: 'admin:mcp' },
  { id: 'hr-evaluation', label: '인사평가', group: '관리', requiredPermission: 'admin:hr_evaluation' },
];

function canAccess(user: AuthUser, item: NavItem): boolean {
  if (!item.requiredPermission) return true;
  const permissions = user.permissions || [];
  return permissions.includes('*') || permissions.includes(item.requiredPermission);
}

export default function App() {
  const [memory, setMemory] = useState<OperationsMemory>(emptyMemory);
  const [status, setStatus] = useState<ApiStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState<Page>('home');
  const [setupRequired, setSetupRequired] = useState(false);
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);

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

  async function bootstrap() {
    setError(null);
    try {
      const setup = await fetchSetupStatus();
      setSetupRequired(setup.setup_required);
      if (!setup.setup_required) {
        const me = await fetchCurrentUser();
        setCurrentUser(me.authenticated ? me.user : null);
      }
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : '알 수 없는 오류가 발생했습니다.');
      setLoading(false);
    }
  }

  useEffect(() => {
    void bootstrap();
  }, []);

  if (loading) {
    return <main className="auth-layout"><section className="panel">로딩 중...</section></main>;
  }

  if (setupRequired) {
    return (
      <>
        {error ? <div className="alert">API 연결 실패: {error}</div> : null}
        <InitialOfficeSetupWizard
          onAuthenticated={(user) => {
            setCurrentUser(user);
            setSetupRequired(false);
            void refresh();
          }}
        />
      </>
    );
  }

  if (!currentUser) {
    return (
      <>
        {error ? <div className="alert">API 연결 실패: {error}</div> : null}
        <AuthPage
          setupRequired={setupRequired}
          onAuthenticated={(user) => {
            setCurrentUser(user);
            setSetupRequired(false);
            void refresh();
          }}
        />
      </>
    );
  }

  const visibleNavItems = navItems.filter((item) => canAccess(currentUser, item));
  const activePageAllowed = visibleNavItems.some((item) => item.id === page);

  return (
    <AppShell page={activePageAllowed ? page : 'profile'} navItems={visibleNavItems} onNavigate={setPage} user={currentUser} onLoggedOut={() => setCurrentUser(null)}>
      {error ? <div className="alert">API 연결 실패: {error}</div> : null}

      {page === 'home' ? <HomePage memory={memory} status={status} onAction={(next) => setPage(next as Page)} /> : null}
      {page === 'profile' || !activePageAllowed ? <UserProfilePage user={currentUser} /> : null}

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
      {page === 'chat' ? <AiAgentPage /> : null}
      {page === 'progress' ? <ProgressLogPage /> : null}
      {page === 'work' ? <WorkItemsPage /> : null}
      {page === 'work-memory' ? <WorkMemoryPage /> : null}
      {page === 'work-architecture' ? <WorkArchitecturePage /> : null}
      {page === 'work-schedule' ? <WorkSchedulePage /> : null}
      {page === 'hiring' ? <HiringPage /> : null}
      {page === 'documents' ? <DocumentAutomationPage /> : null}
      {page === 'handover' ? <HandoverPage /> : null}
      {page === 'integrations' ? <IntegrationsPage /> : null}
      {page === 'uploads' ? <UploadPage /> : null}
      {page === 'admin' ? <AdminSettingsPage /> : null}
      {page === 'access' ? <AccessControlPage /> : null}
      {page === 'hr-evaluation' ? <HrEvaluationPage /> : null}
    </AppShell>
  );
}
