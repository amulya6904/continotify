export default function TeacherCard({ teacher, isSelected, onSelect, onSendAlert, sending, studentCount }) {
  const initials = teacher.name
    .split(' ')
    .map(w => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  return (
    <div
      className={`teacher-card ${isSelected ? 'selected' : ''}`}
      onClick={() => onSelect(teacher)}
    >
      <div className="teacher-avatar">{initials}</div>
      <div className="teacher-info">
        <h3 className="teacher-name">{teacher.name}</h3>
        <p className="teacher-email">{teacher.email || '—'}</p>
      </div>

      {isSelected && studentCount !== null && (
        <div className={`student-count-badge ${studentCount > 0 ? 'badge-warn' : 'badge-ok'}`}>
          {studentCount > 0 ? `${studentCount} low attendance` : 'All on track ✓'}
        </div>
      )}

      <button
        className={`btn btn-alert ${sending ? 'loading' : ''}`}
        disabled={sending || (isSelected && studentCount === 0)}
        onClick={e => {
          e.stopPropagation();
          onSendAlert(teacher.id);
        }}
        title={isSelected && studentCount === 0 ? 'No low-attendance students' : 'Send alert email to this teacher'}
      >
        {sending ? (
          <><span className="spinner-sm" /> Sending…</>
        ) : (
          '✉ Send Alert'
        )}
      </button>
    </div>
  );
}
