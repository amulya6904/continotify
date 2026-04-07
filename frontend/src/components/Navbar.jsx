import { NavLink } from 'react-router-dom';

export default function Navbar() {
  return (
    <nav className="navbar">
      <div className="navbar-brand">
        <span className="navbar-logo">🎓</span>
        <div className="navbar-title">
          <span className="navbar-name">MSRIT Attendance Monitor</span>
          <span className="navbar-sub">Department of Computer Science &amp; Engineering</span>
        </div>
      </div>
      <div className="navbar-links">
        <NavLink to="/" end className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
          Dashboard
        </NavLink>
        <NavLink to="/logs" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
          Alert Logs
        </NavLink>
      </div>
    </nav>
  );
}
