import { useState } from 'react';

function attColor(pct) {
  if (pct === null || pct === undefined) return '';
  if (pct < 65)  return 'att-red';
  if (pct < 75)  return 'att-orange';
  return 'att-green';
}

export default function StudentTable({ students, loading }) {
  const [expanded, setExpanded] = useState(new Set());

  const toggle = usn => {
    setExpanded(prev => {
      const next = new Set(prev);
      next.has(usn) ? next.delete(usn) : next.add(usn);
      return next;
    });
  };

  if (loading) {
    return (
      <div className="table-loading">
        <span className="spinner" />
        <p>Loading students…</p>
      </div>
    );
  }

  if (!students || students.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-icon">✅</div>
        <h3>All students on track</h3>
        <p>No students below the 75% attendance threshold for this teacher.</p>
      </div>
    );
  }

  return (
    <div className="table-container">
      <table className="student-table">
        <thead>
          <tr>
            <th style={{ width: 32 }} />
            <th>Student Name</th>
            <th>USN</th>
            <th>Semester</th>
            <th>Low Subjects</th>
          </tr>
        </thead>
        <tbody>
          {students.map(s => {
            const isOpen = expanded.has(s.usn);
            return (
              <>
                <tr
                  key={s.usn}
                  className={`student-row ${isOpen ? 'expanded' : ''}`}
                  onClick={() => toggle(s.usn)}
                >
                  <td className="expand-cell">{isOpen ? '▼' : '▶'}</td>
                  <td className="student-name-cell">{s.student_name}</td>
                  <td><code>{s.usn}</code></td>
                  <td>{s.semester}</td>
                  <td>
                    <span className="badge badge-warn">{s.low_subjects.length} subject{s.low_subjects.length !== 1 ? 's' : ''}</span>
                  </td>
                </tr>

                {isOpen && (
                  <tr key={`${s.usn}-subjects`} className="subjects-row">
                    <td colSpan={5} className="subjects-cell">
                      <table className="subjects-table">
                        <thead>
                          <tr>
                            <th>Subject</th>
                            <th>Type</th>
                            <th>Attendance %</th>
                            <th>Attended / Total</th>
                          </tr>
                        </thead>
                        <tbody>
                          {s.low_subjects.map((sub, i) => (
                            <tr key={i}>
                              <td>{sub.subject_name}</td>
                              <td><span className="type-badge">{sub.course_type || '—'}</span></td>
                              <td>
                                <span className={`att-pill ${attColor(sub.attendance_percentage)}`}>
                                  {sub.attendance_percentage !== null ? `${sub.attendance_percentage}%` : '—'}
                                </span>
                              </td>
                              <td>{sub.attended_classes ?? '—'} / {sub.total_classes ?? '—'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </td>
                  </tr>
                )}
              </>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
