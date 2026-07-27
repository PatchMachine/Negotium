import { FormEvent, ReactNode, useEffect, useRef, useState } from 'react';

import {
  fetchSetupChatCapability,
  sendSetupChat,
  uploadDocument,
  type CompanyProfile,
  type InitialOfficeSetupResult,
  type SetupChatCapability,
  type SetupChatMessage,
  type UiComponent,
  type UploadRecord,
} from '../../api';

/**
 * The conversational half of the first-run wizard.
 *
 * Admin creation and API-key entry stay deterministic forms — there is no
 * session for the former, and a secret must never be typed into a chat box
 * because chat turns are persisted to the archive. Everything after that
 * (profile → organisation → file analysis → proposed setup) happens here, with
 * the model pulling the relevant form into the conversation itself.
 */

type ChatEntry = SetupChatMessage & {
  id: string;
  surfaces?: UiComponent[];
  tools?: { tool: string; status: string }[];
};

let seq = 0;
const nextId = () => `s${(seq += 1)}`;

const OPENING_PROMPT =
  '안녕하세요. 회사 설정을 시작할게요. 어떤 회사인지 간단히 알려주시거나, 아래 "설정 시작" 버튼을 눌러주세요.';

export default function SetupChatStep({
  companyProfile,
  uploads,
  onUploaded,
  onProposed,
  onFallback,
  renderProfileForm,
}: {
  companyProfile: CompanyProfile;
  uploads: UploadRecord[];
  onUploaded: (record: UploadRecord) => void;
  /** Called when the assistant proposes a setup draft to review. */
  onProposed: (result: InitialOfficeSetupResult) => void;
  /** Called when the configured model cannot drive the conversation. */
  onFallback: (reason: string) => void;
  /**
   * Renders the company-profile form. Passed in rather than imported: the form
   * lives inside the wizard alongside its option tables, and moving it would be
   * a large refactor for no benefit.
   */
  renderProfileForm: (onDone: () => void) => ReactNode;
}) {
  const [capability, setCapability] = useState<SetupChatCapability | null>(null);
  const [entries, setEntries] = useState<ChatEntry[]>([
    { id: nextId(), role: 'assistant', content: OPENING_PROMPT },
  ]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [notice, setNotice] = useState('');
  const [conversationId, setConversationId] = useState('');
  const [draft, setDraft] = useState<InitialOfficeSetupResult | null>(null);
  const threadRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    async function checkCapability() {
      try {
        const result = await fetchSetupChatCapability();
        setCapability(result);
        if (!result.chat_supported) {
          onFallback(result.reasons[0] || '대화형 마법사를 사용할 수 없습니다.');
        }
      } catch (err) {
        onFallback(err instanceof Error ? err.message : '설정 확인 실패');
      }
    }
    void checkCapability();
    // onFallback is stable for the wizard's lifetime.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (threadRef.current) threadRef.current.scrollTop = threadRef.current.scrollHeight;
  }, [entries]);

  async function send(message: string) {
    if (!message.trim() || busy) return;
    const history: SetupChatMessage[] = entries.map((entry) => ({
      role: entry.role,
      content: entry.content,
    }));
    setEntries((current) => [
      ...current,
      { id: nextId(), role: 'user', content: message },
    ]);
    setInput('');
    setBusy(true);
    setNotice('');
    try {
      const response = await sendSetupChat({
        message,
        history,
        company_profile: companyProfile,
        draft,
        conversation_id: conversationId,
      });
      setConversationId(response.conversation_id);
      setEntries((current) => [
        ...current,
        {
          id: nextId(),
          role: 'assistant',
          content: response.answer,
          surfaces: response.ui_components,
          tools: response.tool_invocations.map((item) => ({
            tool: String(item.tool || ''),
            status: String(item.status || ''),
          })),
        },
      ]);
      if (response.result) {
        setDraft(response.result);
        onProposed(response.result);
      }
      if (response.notes.length) setNotice(response.notes.join(' '));
    } catch (err) {
      setNotice(err instanceof Error ? err.message : '설정 대화 실패');
    } finally {
      setBusy(false);
    }
  }

  async function handleFiles(fileList: FileList | null) {
    if (!fileList?.length || busy) return;
    setUploading(true);
    try {
      for (const file of Array.from(fileList)) {
        const form = new FormData();
        form.append('file', file);
        form.append('description', '초기 설정 자료');
        const { upload } = await uploadDocument(form);
        onUploaded(upload);
      }
    } catch (err) {
      setNotice(err instanceof Error ? err.message : '업로드 실패');
      return;
    } finally {
      // Cleared here rather than relying on send()'s finally: send() early
      // returns on an empty message, which used to latch the flag on and
      // disable the whole setup chat permanently.
      setUploading(false);
    }
    await send('파일을 올렸습니다. 내용을 확인해 주세요.');
  }

  /** Setup-only screens the assistant pulls into the conversation. */
  function renderSurface(surface: UiComponent, key: string) {
    if (surface.component === 'setup-profile') {
      return (
        <div className="chat-inline-surface" key={key}>
          <header className="chat-inline-surface-head">
            <strong>{surface.title || '회사 프로필 입력'}</strong>
            <span className="chat-inline-surface-badge">AI가 불러옴</span>
          </header>
          <div className="chat-inline-surface-body">
            {renderProfileForm(() =>
              void send('회사 프로필을 입력했습니다. 다음 단계로 진행해 주세요.'),
            )}
          </div>
        </div>
      );
    }
    if (surface.component === 'setup-files') {
      return (
        <div className="chat-inline-surface" key={key}>
          <header className="chat-inline-surface-head">
            <strong>{surface.title || '회사 자료 업로드'}</strong>
            <span className="chat-inline-surface-badge">AI가 불러옴</span>
          </header>
          <div className="chat-inline-surface-body">
            <input
              type="file"
              multiple
              accept=".csv,.tsv,.xlsx,.txt,.md"
              disabled={busy || uploading}
              onChange={(event) => void handleFiles(event.target.files)}
            />
            {uploads.length ? (
              <ul className="chat-notes">
                {uploads.map((upload) => (
                  <li key={upload.id}>{upload.filename}</li>
                ))}
              </ul>
            ) : null}
          </div>
        </div>
      );
    }
    // setup-review is rendered by the wizard's own review section, which owns
    // the section toggles and the apply button.
    return null;
  }

  if (capability && !capability.chat_supported) return null;

  return (
    <div className="setup-chat">
      {capability ? (
        <p className="muted small">
          {capability.model} 모델이 설정을 도와드립니다.
        </p>
      ) : (
        <p className="muted small">설정 도우미를 준비하는 중입니다...</p>
      )}
      <div className="assistant-thread setup-chat-thread" ref={threadRef}>
        {entries.map((entry) => (
          <div key={entry.id} className={`chat-bubble chat-bubble-${entry.role}`}>
            {entry.content ? <div className="chat-bubble-body">{entry.content}</div> : null}
            {entry.tools?.length ? (
              <ul className="chat-tool-list">
                {entry.tools.map((tool, index) => (
                  <li key={`${entry.id}-t${index}`} className={`chat-tool chat-tool-${tool.status}`}>
                    <code>{tool.tool}</code>
                  </li>
                ))}
              </ul>
            ) : null}
            {entry.surfaces?.map((surface, index) =>
              renderSurface(surface, `${entry.id}-s${index}`),
            )}
          </div>
        ))}
        {busy ? <p className="muted small">생각하는 중...</p> : null}
      </div>
      {notice ? <p className="muted">{notice}</p> : null}
      <form
        className="assistant-composer"
        onSubmit={(event: FormEvent<HTMLFormElement>) => {
          event.preventDefault();
          void send(input.trim());
        }}
      >
        <input
          value={input}
          placeholder="회사에 대해 알려주세요"
          disabled={busy}
          onChange={(event) => setInput(event.target.value)}
        />
        <button type="submit" disabled={busy || !input.trim()}>
          보내기
        </button>
      </form>
      {entries.length <= 1 ? (
        <button
          className="secondary-button"
          type="button"
          disabled={busy}
          onClick={() => void send('설정을 시작해 주세요.')}
        >
          설정 시작
        </button>
      ) : null}
    </div>
  );
}
