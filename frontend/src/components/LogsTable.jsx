import { useState } from 'react';

const PAGE_SIZE = 20;

function fmt(dt) {
  if (!dt) return '—';
  return new Date(dt).toLocaleString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

export default function LogsTable({ logs, loading }) {
  const [page, setPage] = useState(1);

  if (loading) {
    return (
      <div className="table-loading">
        <span className="spinner" />
        <p>Loading logs…</p>
      </div>
    );
  }

  if (!logs || logs.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-icon">📋</div>
        <h3>No alert logs yet</h3>
        <p>Alert logs will appear here after sending notifications from the Dashboard.</p>
      </div>
    );
  }

  const totalPages = Math.ceil(logs.length / PAGE_SIZE);
  const slice = logs.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  return (
    <>
      <div className="logs-meta">
        Showing {slice.length} of {logs.length} records
      </div>

      <div className="table-container">
        <table className="logs-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Recipient</th>
              <th>Teacher Email</th>
              <th>Student</th>
              <th>USN</th>
              <th>Subject</th>
              <th>Attendance %</th>
              <th>Status</th>
              <th>Sent At</th>
            </tr>
          </thead>
          <tbody>
            {slice.map((log, i) => (
              <tr key={log.id}>
                <td className="log-id">{(page - 1) * PAGE_SIZE + i + 1}</td>
                <td>
                  {log.recipient_type === 'teacher'
                    ? <span className="recipient-badge recipient-teacher">👨‍🏫 Teacher</span>
                    : log.recipient_type === 'student'
                    ? <span className="recipient-badge recipient-student">🎓 Student</span>
                    : <span className="recipient-badge">—</span>}
                </td>
                <td className="log-email">{log.teacher_email || '—'}</td>
                <td>{log.student_name || '—'}</td>
                <td><code>{log.usn || '—'}</code></td>
                <td className="log-subject">{log.subject_name || '—'}</td>
                <td>
                  {log.attendance_percentage !== null
                    ? <span className={`att-pill ${log.attendance_percentage < 65 ? 'att-red' : 'att-orange'}`}>
                        {log.attendance_percentage}%
                      </span>
                    : '—'}
                </td>
                <td>
                  <span className={`status-badge status-${log.status}`}>
                    {log.status === 'success' ? '✓ sent' : '✕ failed'}
                  </span>
                </td>
                <td className="log-date">{fmt(log.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="pagination">
          <button className="btn btn-sm" disabled={page === 1} onClick={() => setPage(p => p - 1)}>← Prev</button>
          <span className="page-info">Page {page} of {totalPages}</span>
          <button className="btn btn-sm" disabled={page === totalPages} onClick={() => setPage(p => p + 1)}>Next →</button>
        </div>
      )}
    </>
  );
}
