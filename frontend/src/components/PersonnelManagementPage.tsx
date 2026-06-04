import { useEffect, useState } from 'react';

import {
  createLoginUser,
  deleteDepartment,
  deletePosition,
  deleteUser,
  fetchAccessControl,
  saveDepartment,
  savePosition,
  saveUser,
  type AccessControlPayload,
  type DepartmentRecord,
  type PositionRecord,
  type UserRecord,
} from '../api';
import HrEvaluationPage from './HrEvaluationPage';
import OrgChartGraph from './org/OrgChartGraph';

type PersonnelSection = 'org-chart' | 'assignments' | 'evaluation';

const personnelSections: Array<{ id: PersonnelSection; label: string; description: string }> = [
  { id: 'org-chart', label: '조직도', description: '부서 트리와 상하위 구조 설계' },
  { id: 'assignments', label: '직원 배정', description: '직급 정의와 부서·직급 배정' },
  { id: 'evaluation', label: '인사평가', description: '평가 초안 작성' },
];

const emptyDept: DepartmentRecord = { id: '', name: '', description: '', lead_user_id: '', parent_id: '' };
const emptyPosition: PositionRecord = { id: '', name: '', level: 0, description: '' };
const emptyUser: UserRecord = {
  id: '',
  display_name: '',
  title: '',
  role_id: 'staff',
  active: true,
  department: '',
  position_id: '',
};
const emptyLoginUser = { ...emptyUser, password: '', role_id: 'staff' };

export default function PersonnelManagementPage() {
  const [activeSection, setActiveSection] = useState<PersonnelSection>('org-chart');
  const [acl, setAcl] = useState<AccessControlPayload | null>(null);
  const [dept, setDept] = useState<DepartmentRecord>(emptyDept);
  const [position, setPosition] = useState<PositionRecord>(emptyPosition);
  const [user, setUser] = useState<UserRecord>(emptyUser);
  const [loginUser, setLoginUser] = useState<UserRecord & { password: string }>(emptyLoginUser);
  const [message, setMessage] = useState('');

  async function refresh() {
    try {
      setAcl(await fetchAccessControl());
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '조직 정보 로드 실패');
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  const departments = acl?.departments ?? [];
  const users = acl?.users ?? [];
  const positions = acl?.positions ?? [];
  const roles = acl?.roles ?? [];

  function deptName(id?: string): string {
    if (!id) return '부서 미배정';
    return departments.find((entry) => entry.id === id)?.name ?? '부서 미배정';
  }

  function positionName(id?: string): string {
    if (!id) return '직급 미지정';
    return positions.find((entry) => entry.id === id)?.name ?? '직급 미지정';
  }

  async function submitDepartment() {
    if (!dept.id.trim() || !dept.name.trim()) {
      setMessage('부서 ID와 부서명을 입력하세요.');
      return;
    }
    try {
      setAcl(await saveDepartment({ ...dept, id: dept.id.trim() }));
      setDept(emptyDept);
      setMessage(`부서를 저장했습니다: ${dept.name}`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '부서 저장 실패');
    }
  }

  async function removeDepartment(id: string) {
    try {
      setAcl(await deleteDepartment(id));
      if (dept.id === id) setDept(emptyDept);
      setMessage('부서를 삭제했습니다.');
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '부서 삭제 실패');
    }
  }

  async function submitPosition() {
    if (!position.id.trim() || !position.name.trim()) {
      setMessage('직급 ID와 직급명을 입력하세요.');
      return;
    }
    try {
      setAcl(await savePosition({ ...position, id: position.id.trim() }));
      setPosition(emptyPosition);
      setMessage(`직급을 저장했습니다: ${position.name}`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '직급 저장 실패');
    }
  }

  async function removePosition(id: string) {
    try {
      setAcl(await deletePosition(id));
      if (position.id === id) setPosition(emptyPosition);
      setMessage('직급을 삭제했습니다.');
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '직급 삭제 실패');
    }
  }

  async function submitUser() {
    if (!user.id.trim() || !user.display_name.trim()) {
      setMessage('사원 ID와 이름을 입력하세요.');
      return;
    }
    try {
      setAcl(await saveUser({ ...user, id: user.id.trim() }));
      setUser(emptyUser);
      setMessage(`직원 배정을 저장했습니다: ${user.display_name}`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '직원 배정 저장 실패');
    }
  }

  async function submitLoginUser() {
    if (!loginUser.id.trim() || !loginUser.display_name.trim() || !loginUser.password.trim()) {
      setMessage('로그인 ID, 이름, 초기 비밀번호를 입력하세요.');
      return;
    }
    try {
      const result = await createLoginUser({ ...loginUser, id: loginUser.id.trim() });
      setAcl(result.access_control);
      setLoginUser(emptyLoginUser);
      setMessage(`로그인 계정과 직원 배정을 만들었습니다: ${loginUser.display_name}`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '로그인 계정 생성 실패');
    }
  }

  async function removeUser(id: string) {
    try {
      setAcl(await deleteUser(id));
      if (user.id === id) setUser(emptyUser);
      setMessage('직원을 삭제했습니다.');
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '직원 삭제 실패');
    }
  }

  function editUser(entry: UserRecord) {
    setUser({
      ...entry,
      department: entry.department ?? '',
      position_id: entry.position_id ?? '',
    });
  }

  return (
    <section className="admin-settings-page">
      <div className="panel admin-section-nav-panel">
        <p className="eyebrow">Personnel management</p>
        <h2>인사관리</h2>
        <p className="muted">
          조직도를 직접 설계하고 직원에게 부서와 직급을 배정합니다. 인사평가는 같은 화면의 하위 탭에서 진행합니다.
        </p>
        <nav className="admin-section-nav" aria-label="인사관리 섹션">
          {personnelSections.map((section) => (
            <button
              key={section.id}
              type="button"
              className={activeSection === section.id ? 'active-tab' : 'secondary-button'}
              onClick={() => setActiveSection(section.id)}
            >
              <span>{section.label}</span>
              <small>{section.description}</small>
            </button>
          ))}
        </nav>
      </div>

      {activeSection === 'org-chart' ? (
        <section className="admin-api-grid">
          <div className="panel">
            <p className="eyebrow">Department</p>
            <h2>부서 노드</h2>
            <p className="muted">부서를 만들고 상위 부서를 지정하면 계층형 조직도가 구성됩니다.</p>
            <div className="memory-form org-form">
              <label>
                부서 ID
                <input
                  placeholder="예: product, cs, sales"
                  value={dept.id}
                  onChange={(event) => setDept({ ...dept, id: event.target.value })}
                />
              </label>
              <label>
                부서명
                <input
                  placeholder="예: 제품개발팀"
                  value={dept.name}
                  onChange={(event) => setDept({ ...dept, name: event.target.value })}
                />
              </label>
              <label>
                설명
                <input
                  placeholder="부서 업무 범위"
                  value={dept.description ?? ''}
                  onChange={(event) => setDept({ ...dept, description: event.target.value })}
                />
              </label>
              <label>
                상위 부서
                <select
                  value={dept.parent_id ?? ''}
                  onChange={(event) => setDept({ ...dept, parent_id: event.target.value })}
                >
                  <option value="">최상위(없음)</option>
                  {departments
                    .filter((entry) => entry.id !== dept.id)
                    .map((entry) => (
                      <option key={entry.id} value={entry.id}>
                        {entry.name}
                      </option>
                    ))}
                </select>
              </label>
              <label>
                부서 리드
                <select
                  value={dept.lead_user_id ?? ''}
                  onChange={(event) => setDept({ ...dept, lead_user_id: event.target.value })}
                >
                  <option value="">미지정</option>
                  {users.map((entry) => (
                    <option key={entry.id} value={entry.id}>
                      {entry.display_name}
                    </option>
                  ))}
                </select>
              </label>
              <div className="form-actions">
                <button type="button" onClick={() => void submitDepartment()}>부서 저장</button>
                {dept.id ? (
                  <button type="button" className="secondary-button" onClick={() => setDept(emptyDept)}>
                    초기화
                  </button>
                ) : null}
              </div>
            </div>
          </div>

          <div className="panel">
            <p className="eyebrow">Org chart</p>
            <h2>조직 운영도</h2>
            <p className="muted">
              상위 부서에서 하위 부서로 연결선을 그려 조직 계층을 그래프로 표시합니다. 노드를 클릭하면 왼쪽 폼에서 편집할 수 있습니다.
            </p>
            <OrgChartGraph
              departments={departments}
              users={users}
              selectedId={dept.id}
              onSelect={(id) => {
                const target = departments.find((entry) => entry.id === id);
                if (target) {
                  setDept({
                    ...emptyDept,
                    ...target,
                    description: target.description ?? '',
                    lead_user_id: target.lead_user_id ?? '',
                    parent_id: target.parent_id ?? '',
                  });
                }
              }}
            />
            {dept.id ? (
              <div className="org-selected-actions">
                <p className="muted small">선택된 부서: {dept.name || dept.id}</p>
                <button type="button" className="secondary-button" onClick={() => void removeDepartment(dept.id)}>
                  선택한 부서 삭제
                </button>
              </div>
            ) : null}
          </div>
        </section>
      ) : null}

      {activeSection === 'assignments' ? (
        <section className="admin-api-grid">
          <div className="panel">
            <p className="eyebrow">Positions</p>
            <h2>직급 관리</h2>
            <p className="muted">직급(직위)은 권한 역할과 별개이며, 조직 내 직위 체계를 정의합니다.</p>
            <div className="memory-form org-form">
              <label>
                직급 ID
                <input
                  placeholder="예: staff, lead, director"
                  value={position.id}
                  onChange={(event) => setPosition({ ...position, id: event.target.value })}
                />
              </label>
              <label>
                직급명
                <input
                  placeholder="예: 책임, 수석, 팀장"
                  value={position.name}
                  onChange={(event) => setPosition({ ...position, name: event.target.value })}
                />
              </label>
              <label>
                레벨(높을수록 상위)
                <input
                  type="number"
                  value={position.level}
                  onChange={(event) => setPosition({ ...position, level: Number(event.target.value) })}
                />
              </label>
              <label>
                설명
                <input
                  placeholder="직급 설명"
                  value={position.description ?? ''}
                  onChange={(event) => setPosition({ ...position, description: event.target.value })}
                />
              </label>
              <div className="form-actions">
                <button type="button" onClick={() => void submitPosition()}>직급 저장</button>
                {position.id ? (
                  <button type="button" className="secondary-button" onClick={() => setPosition(emptyPosition)}>
                    초기화
                  </button>
                ) : null}
              </div>
            </div>
            <div className="org-list">
              {positions.length === 0 ? <p className="muted">등록된 직급이 없습니다.</p> : null}
              {[...positions]
                .sort((a, b) => b.level - a.level)
                .map((entry) => (
                  <article className="org-card" key={entry.id}>
                    <div className="org-card-head">
                      <strong>{entry.name}</strong>
                      <span className="status-pill">level {entry.level}</span>
                    </div>
                    <p className="muted">
                      {entry.id}
                      {entry.description ? ` · ${entry.description}` : ''}
                    </p>
                    <div className="form-actions">
                      <button type="button" className="secondary-button" onClick={() => setPosition({ ...entry })}>
                        편집
                      </button>
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={() => void removePosition(entry.id)}
                      >
                        삭제
                      </button>
                    </div>
                  </article>
                ))}
            </div>
          </div>

          <div className="panel">
            <p className="eyebrow">Create account</p>
            <h2>로그인 계정 + 직원 배정</h2>
            <p className="muted">
              직원이 먼저 가입 요청을 보내지 않아도 관리자가 직접 로그인 ID, 초기 비밀번호, 부서, 직급, 권한 역할을 한 번에 만들 수 있습니다.
            </p>
            <div className="memory-form org-form">
              <div className="org-form-row">
                <label>
                  로그인 ID
                  <input
                    placeholder="예: kim.cs01"
                    value={loginUser.id}
                    onChange={(event) => setLoginUser({ ...loginUser, id: event.target.value })}
                  />
                </label>
                <label>
                  초기 비밀번호
                  <input
                    type="password"
                    placeholder="8자 이상"
                    value={loginUser.password}
                    onChange={(event) => setLoginUser({ ...loginUser, password: event.target.value })}
                  />
                </label>
              </div>
              <div className="org-form-row">
                <label>
                  이름
                  <input
                    placeholder="직원 이름"
                    value={loginUser.display_name}
                    onChange={(event) => setLoginUser({ ...loginUser, display_name: event.target.value })}
                  />
                </label>
                <label>
                  직함
                  <input
                    placeholder="예: 문서 관리 담당자"
                    value={loginUser.title}
                    onChange={(event) => setLoginUser({ ...loginUser, title: event.target.value })}
                  />
                </label>
              </div>
              <div className="org-form-row">
                <label>
                  부서
                  <select
                    value={loginUser.department ?? ''}
                    onChange={(event) => setLoginUser({ ...loginUser, department: event.target.value })}
                  >
                    <option value="">부서 미배정</option>
                    {departments.map((entry) => (
                      <option key={entry.id} value={entry.id}>
                        {entry.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  직급
                  <select
                    value={loginUser.position_id ?? ''}
                    onChange={(event) => setLoginUser({ ...loginUser, position_id: event.target.value })}
                  >
                    <option value="">직급 미지정</option>
                    {positions.map((entry) => (
                      <option key={entry.id} value={entry.id}>
                        {entry.name}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <div className="org-form-row">
                <label>
                  권한 역할
                  <select
                    value={loginUser.role_id}
                    onChange={(event) => setLoginUser({ ...loginUser, role_id: event.target.value })}
                  >
                    {roles.map((entry) => (
                      <option key={entry.id} value={entry.id}>
                        {entry.name} (level {entry.level})
                      </option>
                    ))}
                  </select>
                </label>
                <label className="org-checkbox">
                  <input
                    type="checkbox"
                    checked={loginUser.active}
                    onChange={(event) => setLoginUser({ ...loginUser, active: event.target.checked })}
                  />
                  즉시 로그인 가능
                </label>
              </div>
              <div className="form-actions">
                <button type="button" onClick={() => void submitLoginUser()}>
                  계정 생성 + 배정
                </button>
                <button type="button" className="secondary-button" onClick={() => setLoginUser(emptyLoginUser)}>
                  초기화
                </button>
              </div>
            </div>
          </div>

          <div className="panel">
            <p className="eyebrow">Assignments</p>
            <h2>직원 배정</h2>
            <p className="muted">이미 존재하는 직원 레코드를 부서와 직급에 배정합니다. 신규 로그인 계정은 위 폼에서 직접 만듭니다.</p>
            <div className="memory-form org-form">
              <label>
                사원 ID (로그인 계정)
                <input
                  placeholder="user id"
                  value={user.id}
                  onChange={(event) => setUser({ ...user, id: event.target.value })}
                />
              </label>
              <label>
                이름
                <input
                  placeholder="이름"
                  value={user.display_name}
                  onChange={(event) => setUser({ ...user, display_name: event.target.value })}
                />
              </label>
              <label>
                직함
                <input
                  placeholder="예: 백엔드 엔지니어"
                  value={user.title}
                  onChange={(event) => setUser({ ...user, title: event.target.value })}
                />
              </label>
              <div className="org-form-row">
                <label>
                  부서
                  <select
                    value={user.department ?? ''}
                    onChange={(event) => setUser({ ...user, department: event.target.value })}
                  >
                    <option value="">부서 미배정</option>
                    {departments.map((entry) => (
                      <option key={entry.id} value={entry.id}>
                        {entry.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  직급
                  <select
                    value={user.position_id ?? ''}
                    onChange={(event) => setUser({ ...user, position_id: event.target.value })}
                  >
                    <option value="">직급 미지정</option>
                    {positions.map((entry) => (
                      <option key={entry.id} value={entry.id}>
                        {entry.name}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <label className="org-checkbox">
                <input
                  type="checkbox"
                  checked={user.active}
                  onChange={(event) => setUser({ ...user, active: event.target.checked })}
                />
                재직 중(활성)
              </label>
              <div className="form-actions">
                <button type="button" onClick={() => void submitUser()}>배정 저장</button>
                {user.id ? (
                  <button type="button" className="secondary-button" onClick={() => setUser(emptyUser)}>
                    초기화
                  </button>
                ) : null}
              </div>
            </div>
            <div className="org-list">
              {users.map((entry) => (
                <article className="org-card" key={entry.id}>
                  <div className="org-card-head">
                    <strong>{entry.display_name}</strong>
                    <span className={entry.active ? 'status-pill' : 'status-pill status-pill-muted'}>
                      {entry.active ? '재직' : '비활성'}
                    </span>
                  </div>
                  <p className="muted">
                    {entry.id}
                    {entry.title ? ` · ${entry.title}` : ''}
                  </p>
                  <p className="org-tags">
                    <span className="org-tag">{deptName(entry.department)}</span>
                    <span className="org-tag">{positionName(entry.position_id)}</span>
                  </p>
                  <div className="form-actions">
                    <button type="button" className="secondary-button" onClick={() => editUser(entry)}>
                      편집
                    </button>
                    <button type="button" className="secondary-button" onClick={() => void removeUser(entry.id)}>
                      삭제
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>
      ) : null}

      {activeSection === 'evaluation' ? <HrEvaluationPage /> : null}

      {message ? <p className="muted org-message">{message}</p> : null}
    </section>
  );
}
