import { useEffect, useState } from 'react';

import {
  approveAccountRequest,
  deleteRole,
  deleteUser,
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

export default function AccessControlPage() {
  const [acl, setAcl] = useState<AccessControlPayload | null>(null);
  const [requests, setRequests] = useState<AccountRequest[]>([]);
  const [role, setRole] = useState<RoleRecord>({ id: '', name: '', level: 0, permissions: [] });
  const [user, setUser] = useState<UserRecord>({ id: '', display_name: '', title: '', role_id: 'viewer', active: true });

  async function refresh() {
    const [nextAcl, nextRequests] = await Promise.all([fetchAccessControl(), fetchAccountRequests()]);
    setAcl(nextAcl);
    setRequests(nextRequests.requests);
  }

  useEffect(() => {
    void refresh();
  }, []);

  return (
    <section className="page-grid">
      <div className="panel">
        <p className="eyebrow">Roles</p>
        <h2>직급/권한</h2>
        <div className="memory-form">
          <input placeholder="role id" value={role.id} onChange={(event) => setRole({ ...role, id: event.target.value })} />
          <input placeholder="직급명" value={role.name} onChange={(event) => setRole({ ...role, name: event.target.value })} />
          <input placeholder="level" type="number" value={role.level} onChange={(event) => setRole({ ...role, level: Number(event.target.value) })} />
          <div className="permission-grid">
            {acl?.permissions.map((permission) => (
              <label key={permission}>
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
                {permission}
              </label>
            ))}
          </div>
          <button type="button" onClick={() => saveRole(role).then(setAcl)}>직급 저장</button>
        </div>
        <div className="log-list">
          {acl?.roles.map((entry) => (
            <article className="log-card" key={entry.id}>
              <strong>{entry.name}</strong>
              <p>{entry.id} · level {entry.level} · {entry.permissions.join(', ')}</p>
              <button className="secondary-button" type="button" onClick={() => deleteRole(entry.id).then(setAcl)}>삭제</button>
            </article>
          ))}
        </div>
      </div>
      <div className="panel">
        <p className="eyebrow">Users</p>
        <h2>사용자/직함</h2>
        <div className="memory-form">
          <input placeholder="user id" value={user.id} onChange={(event) => setUser({ ...user, id: event.target.value })} />
          <input placeholder="이름" value={user.display_name} onChange={(event) => setUser({ ...user, display_name: event.target.value })} />
          <input placeholder="직함" value={user.title} onChange={(event) => setUser({ ...user, title: event.target.value })} />
          <select value={user.role_id} onChange={(event) => setUser({ ...user, role_id: event.target.value })}>
            {acl?.roles.map((entry) => <option key={entry.id} value={entry.id}>{entry.name}</option>)}
          </select>
          <button type="button" onClick={() => saveUser(user).then(setAcl)}>사용자 저장</button>
        </div>
        <div className="log-list">
          {acl?.users.map((entry) => (
            <article className="log-card" key={entry.id}>
              <strong>{entry.display_name}</strong>
              <p>{entry.id} · {entry.title} · {entry.role_id}</p>
              <button className="secondary-button" type="button" onClick={() => deleteUser(entry.id).then(setAcl)}>삭제</button>
            </article>
          ))}
        </div>
      </div>
      <div className="panel">
        <p className="eyebrow">Account Requests</p>
        <h2>계정 개설 요청</h2>
        <div className="log-list">
          {requests.filter((entry) => entry.status === 'pending').map((entry) => (
            <article className="log-card" key={entry.id}>
              <strong>{entry.display_name}</strong>
              <p>{entry.user_id} · {entry.title || '직함 미입력'} · {entry.created_at}</p>
              <button type="button" onClick={() => approveAccountRequest(entry.id).then(() => void refresh())}>승인</button>
              <button className="secondary-button" type="button" onClick={() => rejectAccountRequest(entry.id).then(() => void refresh())}>거절</button>
            </article>
          ))}
          {requests.filter((entry) => entry.status === 'pending').length === 0 ? (
            <p className="muted">대기 중인 계정 요청이 없습니다.</p>
          ) : null}
        </div>
      </div>
    </section>
  );
}
