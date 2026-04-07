import { useState, useEffect, useCallback } from 'react';
import { api } from '../api';
import LogsTable from '../components/LogsTable';

export default function Logs() {
  const [logs, setLogs]         = useState([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState('');

  const [filterEmail, setFilterEmail]   = useState('');
  const [filterUSN, setFilterUSN]       = useState('');
  const [filterStatus, setFilterStatus] = useState('');

  const loadLogs = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await api.getLogs({
        teacher_email: filterEmail || undefined,
        usn:           filterUSN   || undefined,
        status:        filterStatus || undefined,
        limit: 500,
      });
      setLogs(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [filterEmail, filterUSN, filterStatus]);

  // Load on mount
  useEffect(() => { loadLogs(); }, []);

  const handleClear = () => {
    setFilterEmail('');
    setFilterUSN('');
    setFilterStatus('');
  };

  // Re-fetch when filters change (with a small debounce)
  useEffect(() => {
    const t = setTimeout(() => loadLogs(), 400);
    return () => clearTimeout(t);
  }, [filterEmail, filterUSN, filterStatus]);

  return (
    <div className="page-container">

      <div className="page-header">
        <h1 className="page-title">Alert Logs</h1>
        <p className="page-subtitle">History of all attendance alert emails sent via the notification service</p>
      </div>

      {/* Filters */}
      <div className="filters-bar">
        <input
          className="filter-input"
          placeholder="Filter by teacher email"
          value={filterEmail}
          onChange={e => setFilterEmail(e.target.value)}
        />
        <input
          className="filter-input"
          placeholder="Filter by USN"
          value={filterUSN}
          onChange={e => setFilterUSN(e.target.value.toUpperCase())}
        />
        <select
          className="filter-select"
          value={filterStatus}
          onChange={e => setFilterStatus(e.target.value)}
        >
          <option value="">All statuses</option>
          <option value="success">Success</option>
          <option value="failed">Failed</option>
        </select>
        <button className="btn btn-sm btn-outline" onClick={handleClear}>
          Clear
        </button>
        <button className="btn btn-sm btn-primary" onClick={loadLogs}>
          ↻ Refresh
        </button>
      </div>

      {error && (
        <div className="error-banner">
          ⚠ {error}
          <br /><small>Make sure both backend (port 8000) and notification service (port 8001) are running.</small>
        </div>
      )}

      <LogsTable logs={logs} loading={loading} />
    </div>
  );
}
