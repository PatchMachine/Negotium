import { useEffect, useState } from 'react';

import {
  deleteRole,
  deleteUser,
  fetchAccessControl,
  saveRole,
  saveUser,
  type AccessControlPayload,
  type RoleRecord,
  type UserRecord,
} from '../api';

export default function AccessControlPage() {
  const [acl, setAcl] = useState<AccessControlPayload | null>(null);
  const [role, setRole] = useState<RoleRecord>({ id: '', name: '', level: 0, permissions: [] });
  const [user, setUser] = useState<UserRecord>({ id: '', display_name: '', title: '', role_id: 'viewer', active: true });

  async function refresh() {
    setAcl(await fetchAccessControl());
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
    </section>
  );
}
