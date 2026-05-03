import { useEffect, useState } from 'react';

import { fetchWorkItems, type WorkItemsPayload } from '../api';

export default function WorkItemsPage() {
  const [workItems, setWorkItems] = useState<WorkItemsPayload | null>(null);

  useEffect(() => {
    fetchWorkItems()
      .then(setWorkItems)
      .catch(() => setWorkItems({ items: [], bottleneck_summary: '업무 현황을 불러오지 못했습니다.' }));
  }, []);

  return (
    <section className="panel">
      <p className="eyebrow">Work Items</p>
      <h2>업무 진행중인 사항</h2>
      <pre className="status-pre">{workItems?.bottleneck_summary ?? '병목 요약을 불러오는 중...'}</pre>
      <div className="work-table">
        <div className="work-row work-header">
          <span>업무</span>
          <span>상태</span>
          <span>출처</span>
          <span>로그</span>
        </div>
        {workItems?.items.length === 0 ? <p className="muted">표시할 업무 로그가 없습니다.</p> : null}
        {workItems?.items.map((item) => (
          <div className="work-row" key={item.path}>
            <span>{item.summary || item.title}</span>
            <strong>{item.status || '-'}</strong>
            <span>{item.kind || item.source || '-'}</span>
            <small>{item.path}</small>
          </div>
        ))}
      </div>
    </section>
  );
}
