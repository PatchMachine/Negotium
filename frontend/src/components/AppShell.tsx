import { ReactNode, useEffect, useState } from 'react';

import { getCurrentUserId, setCurrentUserId } from '../auth';
import { applyTheme, getTheme, setTheme, toggleTheme, type Theme } from '../theme';

type NavItem<T extends string> = {
  id: T;
  label: string;
  group: string;
};

type Props<T extends string> = {
  page: T;
  navItems: NavItem<T>[];
  onNavigate: (page: T) => void;
  children: ReactNode;
};

export default function AppShell<T extends string>({ page, navItems, onNavigate, children }: Props<T>) {
  const [userId, setUserId] = useState(getCurrentUserId());
  const [theme, setLocalTheme] = useState<Theme>(getTheme());

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  const onToggleTheme = () => {
    const next = toggleTheme(theme);
    setLocalTheme(next);
    setTheme(next);
  };

  return (
    <div className="site-shell">
      <header className="topbar">
        <div className="topbar-brand">
          <p className="eyebrow">Patch Machine</p>
          <strong>AI Office BPA</strong>
        </div>
        <div className="topbar-actions">
          <button
            type="button"
            className="theme-toggle"
            onClick={onToggleTheme}
            aria-label="테마 전환"
            title={theme === 'dark' ? '라이트 모드' : '다크 모드'}
          >
            {theme === 'dark' ? '라이트 모드' : '다크 모드'}
          </button>
          <label className="user-picker">
            현재 사용자
            <input
              value={userId}
              onChange={(event) => {
                setUserId(event.target.value);
                setCurrentUserId(event.target.value);
              }}
              placeholder="user-id"
            />
          </label>
        </div>
      </header>

      <div className="layout-grid">
        <aside className="sidebar">
          {Array.from(new Set(navItems.map((item) => item.group))).map((group) => (
            <section key={group}>
              <p>{group}</p>
              {navItems
                .filter((item) => item.group === group)
                .map((item) => (
                  <button
                    className={page === item.id ? 'active-tab' : 'secondary-button'}
                    key={item.id}
                    type="button"
                    onClick={() => onNavigate(item.id)}
                  >
                    {item.label}
                  </button>
                ))}
            </section>
          ))}
        </aside>
        <main className="content-panel">{children}</main>
      </div>
    </div>
  );
}
