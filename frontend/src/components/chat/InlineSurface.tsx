import { Suspense, useState } from 'react';

import { surfaceComponents } from './surfaceRegistry';

export type SurfaceRequest = {
  component: string;
  title?: string;
  mode?: 'inline' | 'panel' | 'route';
  props?: Record<string, unknown>;
  /** Why the assistant opened this, or 'nav' when the user clicked the sidebar. */
  reason?: string;
  origin?: 'assistant' | 'nav';
};

/**
 * Renders a feature screen as a card inside the chat thread.
 *
 * Clicking a nav item loads the feature here rather than navigating away, and
 * the assistant can summon the same card via the `ui.open_surface` tool.
 */
export default function InlineSurface({
  surface,
  onClose,
}: {
  surface: SurfaceRequest;
  onClose?: () => void;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const Component = surfaceComponents[surface.component];

  if (!Component) {
    return (
      <div className="chat-inline-surface chat-inline-surface-missing">
        <p className="muted small">
          '{surface.component}' 화면은 채팅 안에서 열 수 없습니다. 사이드바에서 열어주세요.
        </p>
      </div>
    );
  }

  return (
    <section
      className={`chat-inline-surface${surface.mode === 'panel' ? ' chat-inline-surface-panel' : ''}`}
      aria-label={surface.title || surface.component}
    >
      <header className="chat-inline-surface-head">
        <div>
          <strong>{surface.title || surface.component}</strong>
          {surface.origin === 'assistant' ? (
            <span className="chat-inline-surface-badge">AI가 불러옴</span>
          ) : null}
          {surface.reason ? <p className="muted small">{surface.reason}</p> : null}
        </div>
        <div className="chat-inline-surface-actions">
          <button
            className="secondary-button"
            type="button"
            onClick={() => setCollapsed((value) => !value)}
            aria-expanded={!collapsed}
          >
            {collapsed ? '펼치기' : '접기'}
          </button>
          {onClose ? (
            <button className="secondary-button" type="button" onClick={onClose}>
              닫기
            </button>
          ) : null}
        </div>
      </header>
      {collapsed ? null : (
        <div className="chat-inline-surface-body">
          <Suspense fallback={<p className="muted small">화면을 불러오는 중...</p>}>
            {/* The assistant can pass props (e.g. a prefilled draft); dropping
                them silently discarded half the tool payload. */}
            <Component {...(surface.props || {})} />
          </Suspense>
        </div>
      )}
    </section>
  );
}
