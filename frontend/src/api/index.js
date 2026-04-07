const BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  getTeachers: () =>
    request('/teachers'),

  getSummary: () =>
    request('/summary'),

  getLowAttendance: (teacherId) =>
    request(`/low-attendance?teacher_id=${teacherId}`),

  sendAlert: (teacherId, { notifyTeacher = true, notifyStudent = true } = {}) =>
    request(`/alerts/send/${teacherId}`, {
      method: 'POST',
      body: JSON.stringify({ notify_teacher: notifyTeacher, notify_student: notifyStudent }),
    }),

  getLogs: ({ teacher_email, usn, status, limit = 200, skip = 0 } = {}) => {
    const p = new URLSearchParams({ limit, skip });
    if (teacher_email) p.append('teacher_email', teacher_email);
    if (usn)           p.append('usn', usn);
    if (status)        p.append('status', status);
    return request(`/alerts/logs?${p}`);
  },
};
