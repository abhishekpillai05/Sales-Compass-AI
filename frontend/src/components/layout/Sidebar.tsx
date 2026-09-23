import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  MessageSquare,
  Search,
  Upload,
  BarChart2,
  LogOut,
  Compass,
  Menu,
  X,
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { useState } from 'react';

const navItems = [
  { to: '/chat', icon: MessageSquare, label: 'AI Assistant' },
  { to: '/search', icon: Search, label: 'Product Search' },
  { to: '/upload', icon: Upload, label: 'Upload Documents' },
];

const adminNavItems = [
  { to: '/admin', icon: BarChart2, label: 'Query Logs' },
];

export function Sidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const initials = user?.username
    ? user.username.slice(0, 2).toUpperCase()
    : '??';

  return (
    <>
      {/* Mobile toggle */}
      <button
        className="btn btn-ghost btn-icon"
        style={{
          position: 'fixed',
          top: 12,
          left: 12,
          zIndex: 50,
          display: 'none',
        }}
        id="sidebar-mobile-toggle"
        aria-label="Toggle sidebar"
        onClick={() => setMobileOpen(!mobileOpen)}
      >
        {mobileOpen ? <X size={20} /> : <Menu size={20} />}
      </button>

      <aside
        className={`app-sidebar${mobileOpen ? ' open' : ''}`}
        aria-label="Application navigation"
      >
        {/* Logo */}
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon">
            <Compass size={20} color="white" />
          </div>
          <div className="sidebar-logo-text">
            SalesCompass
            <span>AI Assistant</span>
          </div>
        </div>

        {/* Nav */}
        <nav className="sidebar-nav">
          <div className="nav-section-label">Main</div>
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `nav-item${isActive ? ' active' : ''}`
              }
              onClick={() => setMobileOpen(false)}
            >
              <Icon size={17} />
              {label}
            </NavLink>
          ))}

          {user?.role === 'admin' && (
            <>
              <div className="nav-section-label" style={{ marginTop: 8 }}>
                Admin
              </div>
              {adminNavItems.map(({ to, icon: Icon, label }) => (
                <NavLink
                  key={to}
                  to={to}
                  className={({ isActive }) =>
                    `nav-item${isActive ? ' active' : ''}`
                  }
                  onClick={() => setMobileOpen(false)}
                >
                  <Icon size={17} />
                  {label}
                </NavLink>
              ))}
            </>
          )}
        </nav>

        {/* Footer / User */}
        <div className="sidebar-footer">
          {user && (
            <div className="user-chip" style={{ marginBottom: 8 }}>
              <div className="user-avatar">{initials}</div>
              <div className="user-info">
                <div className="user-name">{user.username}</div>
                <div className="user-role">{user.role}</div>
              </div>
            </div>
          )}
          <button
            className="nav-item"
            onClick={handleLogout}
            style={{ width: '100%', color: '#f87171' }}
            aria-label="Log out"
          >
            <LogOut size={17} />
            Log out
          </button>
        </div>
      </aside>
    </>
  );
}
