import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ToastProvider } from './context/ToastContext';
import Navbar from './components/Navbar';
import Dashboard from './pages/Dashboard';
import Logs from './pages/Logs';
import './App.css';

export default function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <Navbar />
        <main className="main-content">
          <Routes>
            <Route path="/"     element={<Dashboard />} />
            <Route path="/logs" element={<Logs />} />
            <Route path="*"     element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </BrowserRouter>
    </ToastProvider>
  );
}
