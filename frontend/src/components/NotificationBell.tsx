import { useEffect, useRef, useState } from 'react';

import {
  fetchNotifications,
  markNotificationsRead,
  type NotificationItem,
} from '../api';

const POLL_MS = 60_000;

export default function NotificationBell() {
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement | null>(null);

  async function refresh() {
    try {
      const payload = await fetchNotifications();
      setItems(payload.items);
      setUnread(payload.unread);
    } catch {
      // Errors are swallowed: session expiry is handled globally in http.ts,
      // and a transient fetch failure should not surface in the topbar.
    }
  }

  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), POLL_MS);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    function onClickOutside(event: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, []);

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next && unread > 0) {
      // mark_read is idempotent server-side, so sending every visible id is
      // safe and avoids tracking the current user id here.
      try {
        await markNotificationsRead(items.map((item) => item.id));
      } catch {
        // best-effort
      }
      await refresh();
    }
  }

  return (
    <div className="notification-bell" ref={wrapperRef}>
      <button
        type="button"
        className="secondary-button"
        aria-label="알림"
        title="알림"
        onClick={() => void toggle()}
      >
        🔔{unread > 0 ? <span className="notification-badge">{unread}</span> : null}
      </button>
      {open ? (
        <div className="notification-dropdown">
          {items.length === 0 ? (
            <p className="muted small">알림이 없습니다.</p>
          ) : (
            items.slice(0, 20).map((item) => (
              <div key={item.id} className="notification-item">
                <strong>{item.title}</strong>
                {item.body ? <p className="small">{item.body}</p> : null}
                {item.link_path ? <p className="muted small">{item.link_path}</p> : null}
                <p className="muted small">{item.created_at.slice(0, 16).replace('T', ' ')}</p>
              </div>
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}
