import { useEffect, useState } from 'react';

import {
  createWorkScheduleItem,
  deleteWorkScheduleItem,
  fetchWorkSchedule,
  generateWorkSchedule,
  updateWorkScheduleItem,
  type WorkScheduleItem,
} from '../api';

const emptyItem: WorkScheduleItem = {
  id: '',
  title: '',
  owner_id: '',
  owner_name: '',
  status: 'todo',
  priority: 'normal',
  start_date: '',
  due_date: '',
  dependencies: [],
  notes: '',
  source_architecture_id: '',
};

export default function WorkSchedulePage() {
  const [items, setItems] = useState<WorkScheduleItem[]>([]);
  const [draft, setDraft] = useState<WorkScheduleItem>(emptyItem);
  const [generator, setGenerator] = useState({ objective: '', participants: '', horizon: '', constraints: '' });
  const [message, setMessage] = useState('');

  async function refresh() {
    const payload = await fetchWorkSchedule();
    setItems(payload.items);
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function save() {
    const result = draft.id ? await updateWorkScheduleItem(draft) : await createWorkScheduleItem(draft);
    setItems(result.items);
    setDraft(emptyItem);
  }

  async function generate() {
    const doc = await generateWorkSchedule(generator);
    setMessage(`AI 스케줄 문서 저장됨: ${doc.path}`);
    await refresh();
  }

  return (
    <section className="page-grid">
      <div className="panel">
        <p className="eyebrow">Schedule</p>
        <h2>작업자별 작업 스케줄</h2>
        <div className="memory-form">
          <input placeholder="업무 제목" value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} />
          <input placeholder="담당자" value={draft.owner_name} onChange={(event) => setDraft({ ...draft, owner_name: event.target.value })} />
          <select value={draft.status} onChange={(event) => setDraft({ ...draft, status: event.target.value })}>
            <option value="todo">todo</option>
            <option value="in_progress">in_progress</option>
            <option value="blocked">blocked</option>
            <option value="done">done</option>
            <option value="cancelled">cancelled</option>
          </select>
          <select value={draft.priority} onChange={(event) => setDraft({ ...draft, priority: event.target.value })}>
            <option value="low">low</option>
            <option value="normal">normal</option>
            <option value="high">high</option>
            <option value="urgent">urgent</option>
          </select>
          <input placeholder="시작일" value={draft.start_date} onChange={(event) => setDraft({ ...draft, start_date: event.target.value })} />
          <input placeholder="마감일" value={draft.due_date} onChange={(event) => setDraft({ ...draft, due_date: event.target.value })} />
          <textarea placeholder="메모" value={draft.notes} onChange={(event) => setDraft({ ...draft, notes: event.target.value })} />
          <button type="button" onClick={() => void save()}>{draft.id ? '수정' : '추가'}</button>
        </div>
        <div className="log-list">
          {items.map((item) => (
            <article className="log-card" key={item.id}>
              <strong>{item.title}</strong>
              <p>{item.owner_name || '-'} · {item.status} · {item.priority} · {item.due_date || '마감 미정'}</p>
              <button className="secondary-button" type="button" onClick={() => setDraft(item)}>편집</button>
              <button className="secondary-button" type="button" onClick={() => deleteWorkScheduleItem(item.id).then((result) => setItems(result.items))}>삭제</button>
            </article>
          ))}
        </div>
      </div>
      <div className="panel">
        <p className="eyebrow">AI Scheduler</p>
        <h2>AI 스케줄 생성</h2>
        <div className="memory-form">
          <input placeholder="목표" value={generator.objective} onChange={(event) => setGenerator({ ...generator, objective: event.target.value })} />
          <textarea placeholder="참여자" value={generator.participants} onChange={(event) => setGenerator({ ...generator, participants: event.target.value })} />
          <input placeholder="기간" value={generator.horizon} onChange={(event) => setGenerator({ ...generator, horizon: event.target.value })} />
          <textarea placeholder="제약" value={generator.constraints} onChange={(event) => setGenerator({ ...generator, constraints: event.target.value })} />
          <button type="button" onClick={() => void generate()}>AI 스케줄 생성</button>
          {message ? <p className="muted">{message}</p> : null}
        </div>
      </div>
    </section>
  );
}
