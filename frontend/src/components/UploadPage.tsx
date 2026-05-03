import { FormEvent, useEffect, useState } from 'react';

import { deleteUpload, fetchUploads, uploadDocument, type UploadRecord } from '../api';

export default function UploadPage() {
  const [uploads, setUploads] = useState<UploadRecord[]>([]);

  async function refresh() {
    setUploads((await fetchUploads()).uploads);
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await uploadDocument(new FormData(event.currentTarget));
    event.currentTarget.reset();
    await refresh();
  }

  return (
    <section className="page-grid">
      <div className="panel">
        <p className="eyebrow">Uploads</p>
        <h2>문서 업로드</h2>
        <form className="memory-form" onSubmit={handleSubmit}>
          <input name="file" type="file" required />
          <input name="work_title" placeholder="업무명" />
          <input name="tags" placeholder="태그" />
          <textarea name="description" placeholder="설명" />
          <button type="submit">업로드</button>
        </form>
      </div>
      <div className="panel">
        <p className="eyebrow">Archive</p>
        <h2>업로드 목록</h2>
        <div className="log-list">
          {uploads.map((upload) => (
            <article className="log-card" key={upload.id}>
              <strong>{upload.filename}</strong>
              <p>{upload.work_title || '업무 미지정'} · {upload.tags || '태그 없음'}</p>
              <small>{upload.path}</small>
              <button className="secondary-button" type="button" onClick={() => deleteUpload(upload.id).then(refresh)}>삭제</button>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
