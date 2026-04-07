import { useState, useEffect, useCallback } from 'react';
import { api } from '../api';
import { useToast } from '../context/ToastContext';
import TeacherCard from '../components/TeacherCard';
import StudentTable from '../components/StudentTable';

export default function Dashboard() {
  const showToast = useToast();

  const [teachers, setTeachers]               = useState([]);
  const [summary, setSummary]                 = useState(null);
  const [selectedTeacher, setSelectedTeacher] = useState(null);
  const [lowStudents, setLowStudents]         = useState([]);
  const [loadingTeachers, setLoadingTeachers] = useState(true);
  const [loadingStudents, setLoadingStudents] = useState(false);
  const [sendingId, setSendingId]             = useState(null);
  const [error, setError]                     = useState('');

  // Notification preference flags
  const [notifyTeacher, setNotifyTeacher] = useState(true);
  const [notifyStudent, setNotifyStudent] = useState(true);

  useEffect(() => {
    Promise.all([
      api.getTeachers(),
      api.getSummary(),
    ])
      .then(([t, s]) => { setTeachers(t); setSummary(s); })
      .catch(err => setError(err.message))
      .finally(() => setLoadingTeachers(false));
  }, []);

  const selectTeacher = useCallback(async (teacher) => {
    if (selectedTeacher?.id === teacher.id) {
      setSelectedTeacher(null);
      setLowStudents([]);
      return;
    }
    setSelectedTeacher(teacher);
    setLowStudents([]);
    setLoadingStudents(true);
    try {
      const data = await api.getLowAttendance(teacher.id);
      setLowStudents(data);
    } catch (err) {
      showToast(`Failed to load students: ${err.message}`, 'error');
    } finally {
      setLoadingStudents(false);
    }
  }, [selectedTeacher, showToast]);

  const sendAlert = useCallback(async (teacherId) => {
    if (!notifyTeacher && !notifyStudent) {
      showToast('Select at least one notification target (Teacher or Student)', 'error');
      return;
    }
    setSendingId(teacherId);
    try {
      const result = await api.sendAlert(teacherId, { notifyTeacher, notifyStudent });
      if (result.status === 'success') {
        showToast(
          `✓ Alert sent to ${result.teacher_name} — ${result.emails_sent} email(s) dispatched`,
          'success',
        );
      } else if (result.status === 'skipped') {
        showToast('No low-attendance students found — no email sent', 'info');
      } else if (result.status === 'partial') {
        showToast(`Partial: ${result.detail}`, 'info');
      } else {
        showToast(`Failed: ${result.detail}`, 'error');
      }
    } catch (err) {
      showToast(`Error: ${err.message}`, 'error');
    } finally {
      setSendingId(null);
    }
  }, [notifyTeacher, notifyStudent, showToast]);

  return (
    <div className="page-container">

      {/* Page header */}
      <div className="page-header">
        <h1 className="page-title">Attendance Dashboard</h1>
        <p className="page-subtitle">Select a teacher to view low-attendance students and send alerts</p>
      </div>

      {/* Summary stats */}
      {summary && (
        <div className="stats-row">
          <div className="stat-card">
            <span className="stat-value">{summary.total_teachers}</span>
            <span className="stat-label">Teachers</span>
          </div>
          <div className="stat-card">
            <span className="stat-value">{summary.total_students}</span>
            <span className="stat-label">Students</span>
          </div>
          <div className="stat-card stat-warn">
            <span className="stat-value">{summary.low_attendance_students}</span>
            <span className="stat-label">Below {summary.threshold}%</span>
          </div>
          <div className="stat-card">
            <span className="stat-value">
              {summary.average_attendance !== null ? `${summary.average_attendance}%` : '—'}
            </span>
            <span className="stat-label">Avg Attendance</span>
          </div>
          {summary.last_scraped_at && (
            <div className="stat-card stat-info">
              <span className="stat-value stat-date">
                {new Date(summary.last_scraped_at).toLocaleDateString('en-IN')}
              </span>
              <span className="stat-label">Last Scraped</span>
            </div>
          )}
        </div>
      )}

      {/* Notification settings panel */}
      <div className="notify-settings-panel">
        <span className="notify-settings-label">Notify via email:</span>
        <label className="notify-checkbox-label">
          <input
            type="checkbox"
            className="notify-checkbox"
            checked={notifyTeacher}
            onChange={e => setNotifyTeacher(e.target.checked)}
          />
          <span className="notify-checkbox-text">
            <span className="notify-checkbox-icon">👨‍🏫</span>
            Teacher (summary)
          </span>
        </label>
        <label className="notify-checkbox-label">
          <input
            type="checkbox"
            className="notify-checkbox"
            checked={notifyStudent}
            onChange={e => setNotifyStudent(e.target.checked)}
          />
          <span className="notify-checkbox-text">
            <span className="notify-checkbox-icon">🎓</span>
            Students (personalized)
          </span>
        </label>
        {!notifyTeacher && !notifyStudent && (
          <span className="notify-warn-hint">⚠ Select at least one</span>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="error-banner">
          ⚠ Could not connect to backend: {error}
          <br /><small>Make sure the backend is running at {import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}</small>
        </div>
      )}

      {/* Teachers grid */}
      {loadingTeachers ? (
        <div className="table-loading"><span className="spinner" /><p>Loading teachers…</p></div>
      ) : teachers.length === 0 && !error ? (
        <div className="empty-state">
          <div className="empty-icon">👨‍🏫</div>
          <h3>No teachers found</h3>
          <p>Add teachers using <code>python3 scripts/add_teacher.py</code> in the scraper directory.</p>
        </div>
      ) : (
        <div className="teachers-grid">
          {teachers.map(t => (
            <TeacherCard
              key={t.id}
              teacher={t}
              isSelected={selectedTeacher?.id === t.id}
              onSelect={selectTeacher}
              onSendAlert={sendAlert}
              sending={sendingId === t.id}
              studentCount={selectedTeacher?.id === t.id ? lowStudents.length : null}
            />
          ))}
        </div>
      )}

      {/* Student section */}
      {selectedTeacher && (
        <div className="student-section">
          <div className="student-section-header">
            <h2>
              Low Attendance Students
              <span className="section-teacher-name"> — {selectedTeacher.name}</span>
            </h2>
            <p className="section-hint">Click a row to expand and view individual subject details</p>
          </div>
          <StudentTable students={lowStudents} loading={loadingStudents} />
        </div>
      )}

    </div>
  );
}
