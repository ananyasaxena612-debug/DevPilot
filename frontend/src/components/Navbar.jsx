import { useState, useEffect } from "react";
import { NavLink, Link } from "react-router-dom";
import {
  Activity,
  Box,
  FileSearch,
  Home,
  Sun,
  Moon,
  Menu,
  X,
  Zap,
  Server,
  Radio,
  Clock
} from "lucide-react";
import { useTheme } from "../context/ThemeContext";
import { getBackendStatus } from "../services/api";

export default function Navbar() {
  const { theme, toggleTheme } = useTheme();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [aiOnline, setAiOnline] = useState(false);
  const [backendOnline, setBackendOnline] = useState(false);

  // Poll status every 8 seconds
  useEffect(() => {
    let isMounted = true;

    const checkStatus = async () => {
      try {
        const data = await getBackendStatus();
        if (isMounted) {
          setBackendOnline(data.backend === "online" || data.status === "online");
          setAiOnline(data.ai === "online");
        }
      } catch {
        if (isMounted) {
          setBackendOnline(false);
          setAiOnline(false);
        }
      }
    };

    checkStatus();
    const interval = setInterval(checkStatus, 8000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const closeMobileMenu = () => setMobileMenuOpen(false);

  // Close mobile drawer on desktop resize or Esc key
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth > 1024) {
        setMobileMenuOpen(false);
      }
    };
    const handleKeyDown = (e) => {
      if (e.key === "Escape") {
        setMobileMenuOpen(false);
      }
    };

    window.addEventListener("resize", handleResize);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("resize", handleResize);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  return (
    <header className="navbar-wrapper">
      <div className="navbar-container">
        {/* Brand / Logo */}
        <Link to="/" className="brand-logo" onClick={closeMobileMenu} aria-label="DevPilot Home">
          <div className="logo-badge">
            <Zap className="logo-svg" size={20} />
          </div>
          <div className="brand-text">
            <span className="brand-name">DevPilot</span>
            <span className="brand-tagline">DevOps Suite</span>
          </div>
        </Link>

        {/* Desktop Navigation Links */}
        <nav className="nav-links desktop-only" aria-label="Main Navigation">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              `nav-item ${isActive ? "nav-item-active" : ""}`
            }
          >
            <Home size={17} />
            <span>Home</span>
          </NavLink>

          <NavLink
            to="/monitoring"
            className={({ isActive }) =>
              `nav-item ${isActive ? "nav-item-active" : ""}`
            }
          >
            <Activity size={17} />
            <span>Monitoring</span>
          </NavLink>

          <NavLink
            to="/docker"
            className={({ isActive }) =>
              `nav-item ${isActive ? "nav-item-active" : ""}`
            }
          >
            <Box size={17} />
            <span>Docker</span>
          </NavLink>

          <NavLink
            to="/analyze"
            className={({ isActive }) =>
              `nav-item ${isActive ? "nav-item-active" : ""}`
            }
          >
            <FileSearch size={17} />
            <span>Log Analysis</span>
          </NavLink>

          <NavLink
            to="/incidents"
            className={({ isActive }) =>
              `nav-item ${isActive ? "nav-item-active" : ""}`
            }
          >
            <Clock size={17} />
            <span>Incident Time Machine</span>
          </NavLink>
        </nav>

        {/* Right Actions: System Status & Theme Toggle */}
        <div className="navbar-right desktop-only">
          {/* Status Badges */}
          <div className="status-indicators">
            <div
              className={`status-pill ${aiOnline ? "pill-online" : "pill-offline"}`}
              title={aiOnline ? "AI Engine (Ollama) is active" : "AI Engine is offline"}
            >
              <span className="status-pulse-dot" />
              <span>{aiOnline ? "AI Online" : "AI Offline"}</span>
            </div>

            <div
              className={`status-pill ${backendOnline ? "pill-online" : "pill-offline"}`}
              title={backendOnline ? "DevPilot Backend reachable" : "Backend unreachable"}
            >
              <Radio size={12} className="status-mini-icon" />
              <span>{backendOnline ? "Backend Live" : "Backend Offline"}</span>
            </div>
          </div>

          {/* Theme Switcher Button */}
          <button
            className="theme-toggle-btn"
            onClick={toggleTheme}
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
            title={`Switch to ${theme === "dark" ? "Light" : "Dark"} mode`}
          >
            {theme === "dark" ? (
              <>
                <Sun size={17} className="theme-icon sun-icon" />
                <span className="theme-text">Light</span>
              </>
            ) : (
              <>
                <Moon size={17} className="theme-icon moon-icon" />
                <span className="theme-text">Dark</span>
              </>
            )}
          </button>
        </div>

        {/* Mobile Hamburger Button */}
        <div className="mobile-actions mobile-only">
          <button
            className="theme-toggle-btn-compact"
            onClick={toggleTheme}
            aria-label="Toggle Theme"
          >
            {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
          </button>

          <button
            className="mobile-menu-btn"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label={mobileMenuOpen ? "Close menu" : "Open menu"}
          >
            {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>
      </div>

      {/* Mobile Menu Dropdown & Backdrop */}
      {mobileMenuOpen && (
        <>
          <div className="mobile-menu-backdrop mobile-only" onClick={closeMobileMenu} />
          <div className="mobile-menu-drawer mobile-only">
            <nav className="mobile-nav-links">
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                `mobile-nav-item ${isActive ? "mobile-nav-item-active" : ""}`
              }
              onClick={closeMobileMenu}
            >
              <Home size={18} />
              <span>Home</span>
            </NavLink>

            <NavLink
              to="/monitoring"
              className={({ isActive }) =>
                `mobile-nav-item ${isActive ? "mobile-nav-item-active" : ""}`
              }
              onClick={closeMobileMenu}
            >
              <Activity size={18} />
              <span>System Monitoring</span>
            </NavLink>

            <NavLink
              to="/docker"
              className={({ isActive }) =>
                `mobile-nav-item ${isActive ? "mobile-nav-item-active" : ""}`
              }
              onClick={closeMobileMenu}
            >
              <Box size={18} />
              <span>Docker Monitoring</span>
            </NavLink>

            <NavLink
              to="/analyze"
              className={({ isActive }) =>
                `mobile-nav-item ${isActive ? "mobile-nav-item-active" : ""}`
              }
              onClick={closeMobileMenu}
            >
              <FileSearch size={18} />
              <span>AI Log Analysis</span>
            </NavLink>

            <NavLink
              to="/incidents"
              className={({ isActive }) =>
                `mobile-nav-item ${isActive ? "mobile-nav-item-active" : ""}`
              }
              onClick={closeMobileMenu}
            >
              <Clock size={18} />
              <span>Incident Time Machine</span>
            </NavLink>
          </nav>

          <div className="mobile-status-section">
            <div className={`status-pill ${aiOnline ? "pill-online" : "pill-offline"}`}>
              <span className="status-pulse-dot" />
              <span>{aiOnline ? "AI Engine Online" : "AI Engine Offline"}</span>
            </div>
            <div className={`status-pill ${backendOnline ? "pill-online" : "pill-offline"}`}>
              <Server size={14} />
              <span>{backendOnline ? "Backend Live" : "Backend Offline"}</span>
            </div>
          </div>
        </div>
      </>
    )}
  </header>
  );
}

