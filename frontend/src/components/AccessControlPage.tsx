import { useEffect, useState } from 'react';

import {
  approveAccountRequest,
  deleteRole,
  fetchAccountRequests,
  fetchAccessControl,
  rejectAccountRequest,
  saveRole,
  saveUser,
  type AccountRequest,
  type AccessControlPayload,
  type RoleRecord,
  type UserRecord,
} from '../api';

const emptyRole: RoleRecord = { id: '', name: '', level: 0, permissions: [] };

export default function AccessControlPage() {
  const [acl, setAcl] = useState<AccessControlPayload | null>(null);
  const [requests, setRequests] = useState<AccountRequest[]>([]);
  const [role, setRole] = useState<RoleRecord>(emptyRole);
  const [message, setMessage] = useState('');

  async function refresh() {
    const [nextAcl, nextRequests] = await Promise.all([fetchAccessControl(), fetchAccountRequests()]);
    setAcl(nextAcl);
    setRequests(nextRequests.requests);
  }

  useEffect(() => {
    void refresh();
  }, []);

  const users = acl?.users ?? [];
  const roles = acl?.roles ?? [];

  function roleName(id?: string): string {
    return roles.find((entry) => entry.id === id)?.name ?? id ?? '';
  }

  function isAdminRole(roleId: string): boolean {
    const target = roles.find((entry) => entry.id === roleId);
    return Boolean(target?.permissions.includes('*') || target?.permissions.includes('admin:users'));
  }

  function isLastActiveAdmin(user: UserRecord): boolean {
    if (!user.active || !isAdminRole(user.role_id)) return false;
    return users.filter((entry) => entry.active && isAdminRole(entry.role_id)).length <= 1;
  }

  async function assignRole(target: UserRecord, roleId: string) {
    try {
      setAcl(await saveUser({ ...target, role_id: roleId }));
      setMessage(`${target.display_name}의 권한 역할을 ${roleName(roleId)}(으)로 변경했습니다.`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '권한 역할 변경 실패');
    }
  }

  return (
    <section className="page-grid org-grid">
      <div className="panel">
        <p className="eyebrow">Roles</p>
        <h2>권한 역할</h2>
        <p className="muted">
          권한 역할은 기능 접근 권한을 정의합니다. 부서·직급 등 조직 구조는 인사관리 화면에서 별도로 관리합니다.
        </p>
        <div className="memory-form org-form">
          <label>
            권한 ID
            <input placeholder="role id" value={role.id} onChange={(event) => setRole({ ...role, id: event.target.value })} />
          </label>
          <label>
            역할명
            <input placeholder="역할명" value={role.name} onChange={(event) => setRole({ ...role, name: event.target.value })} />
          </label>
          <label>
            레벨
            <input placeholder="level" type="number" value={role.level} onChange={(event) => setRole({ ...role, level: Number(event.target.value) })} />
          </label>
          <div className="permission-grid">
            {acl?.permissions.map((permission) => (
              <label key={permission} className="permission-item">
                <input
                  type="checkbox"
                  checked={role.permissions.includes(permission)}
                  onChange={(event) =>
                    setRole({
                      ...role,
                      permissions: event.target.checked
                        ? [...role.permissions, permission]
                        : role.permissions.filter((entry) => entry !== permission),
                    })
                  }
                />
                <span>{permission}</span>
              </label>
            ))}
          </div>
          <div className="form-actions">
            <button type="button" onClick={() => saveRole(role).then(setAcl)}>역할 저장</button>
            {role.id ? <button type="button" className="secondary-button" onClick={() => setRole(emptyRole)}>초기화</button> : null}
          </div>
        </div>
        <div className="org-list">
          {roles.map((entry) => (
            <article className="org-card" key={entry.id}>
              <div className="org-card-head">
                <strong>{entry.name}</strong>
                <span className="status-pill">level {entry.level}</span>
              </div>
              <p className="muted org-permissions">{entry.id} · {entry.permissions.join(', ')}</p>
              <div className="form-actions">
                <button type="button" className="secondary-button" onClick={() => setRole(entry)}>편집</button>
                <button type="button" className="secondary-button" onClick={() => deleteRole(entry.id).then(setAcl)}>삭제</button>
              </div>
            </article>
          ))}
        </div>
      </div>

      <div className="panel">
        <p className="eyebrow">Role assignment</p>
        <h2>권한 역할 배정</h2>
        <p className="muted">직원별 기능 접근 권한 역할을 지정합니다. 부서·직급 배정은 인사관리에서 진행합니다.</p>
        <div className="org-list">
          {users.length === 0 ? <p className="muted">등록된 직원이 없습니다.</p> : null}
          {users.map((entry) => (
            <article className="org-card" key={entry.id}>
              <div className="org-card-head">
                <strong>{entry.display_name}</strong>
                <span className={entry.active ? 'status-pill' : 'status-pill status-pill-muted'}>{entry.active ? '재직' : '비활성'}</span>
              </div>
              <p className="muted">{entry.id}{entry.title ? ` · ${entry.title}` : ''}</p>
              {isLastActiveAdmin(entry) ? (
                <p className="status-pill warn">마지막 관리자: 직원 등급으로 내릴 수 없습니다.</p>
              ) : null}
              <label>
                권한 역할
                <select value={entry.role_id} onChange={(event) => void assignRole(entry, event.target.value)}>
                  {roles.map((roleEntry) => (
                    <option
                      key={roleEntry.id}
                      value={roleEntry.id}
                      disabled={isLastActiveAdmin(entry) && !isAdminRole(roleEntry.id)}
                    >
                      {roleEntry.name}
                    </option>
                  ))}
                </select>
              </label>
            </article>
          ))}
        </div>
      </div>

      <div className="panel">
        <p className="eyebrow">Account Requests</p>
        <h2>계정 개설 요청</h2>
        <div className="org-list">
          {requests.filter((entry) => entry.status === 'pending').map((entry) => (
            <article className="org-card" key={entry.id}>
              <strong>{entry.display_name}</strong>
              <p className="muted">{entry.user_id} · {entry.title || '직함 미입력'} · {entry.created_at}</p>
              <div className="form-actions">
                <button type="button" onClick={() => approveAccountRequest(entry.id).then(() => void refresh())}>승인</button>
                <button className="secondary-button" type="button" onClick={() => rejectAccountRequest(entry.id).then(() => void refresh())}>거절</button>
              </div>
            </article>
          ))}
          {requests.filter((entry) => entry.status === 'pending').length === 0 ? (
            <p className="muted">대기 중인 계정 요청이 없습니다.</p>
          ) : null}
        </div>
      </div>

      {message ? <p className="muted org-message">{message}</p> : null}
    </section>
  );
}
