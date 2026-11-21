import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { X, Mail, Lock, User, LogIn, UserPlus, AlertCircle } from "lucide-react";

export default function AuthModal({ isOpen, onClose }) {
  const { login, register } = useAuth();
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      if (isRegister) {
        if (!name.trim()) {
          throw new Error("Please enter your name");
        }
        await register(email, password, name);
      } else {
        await login(email, password);
      }
      onClose();
    } catch (err) {
      setError(err.message || "Authentication failed. Please verify credentials.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="devpilot-modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <div
        className="devpilot-modal-card auth-modal-card"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="devpilot-modal-header">
          <div>
            <h2 className="devpilot-modal-title">
              {isRegister ? "Create DevPilot Account" : "DevPilot Operator Sign In"}
            </h2>
            <p className="devpilot-modal-subtitle">
              {isRegister
                ? "Register your workspace to manage Linux servers and telemetry"
                : "Sign in with your operator credentials to manage infrastructure"}
            </p>
          </div>
          <button
            type="button"
            className="devpilot-modal-close"
            onClick={onClose}
            aria-label="Close modal"
          >
            <X size={20} />
          </button>
        </div>

        {error && (
          <div className="devpilot-banner devpilot-banner-error" style={{ marginBottom: "1rem" }}>
            <AlertCircle size={18} />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="auth-form">
          {isRegister && (
            <div className="form-group">
              <label htmlFor="auth-name">Full Name</label>
              <div className="input-with-icon">
                <User className="input-icon" size={16} />
                <input
                  id="auth-name"
                  type="text"
                  placeholder="e.g. Sarah Connor"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required={isRegister}
                />
              </div>
            </div>
          )}

          <div className="form-group">
            <label htmlFor="auth-email">Email Address</label>
            <div className="input-with-icon">
              <Mail className="input-icon" size={16} />
              <input
                id="auth-email"
                type="email"
                placeholder="operator@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="auth-password">Password</label>
            <div className="input-with-icon">
              <Lock className="input-icon" size={16} />
              <input
                id="auth-password"
                type="password"
                placeholder="At least 6 characters"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
              />
            </div>
          </div>

          <div className="auth-actions" style={{ marginTop: "1.5rem" }}>
            <button
              type="submit"
              className="btn btn-primary btn-block"
              disabled={loading}
              style={{ width: "100%", justifyContent: "center" }}
            >
              {loading ? (
                <span>Authenticating...</span>
              ) : isRegister ? (
                <>
                  <UserPlus size={18} /> <span>Create Account</span>
                </>
              ) : (
                <>
                  <LogIn size={18} /> <span>Sign In</span>
                </>
              )}
            </button>
          </div>

          <div className="auth-switch" style={{ textAlign: "center", marginTop: "1rem" }}>
            {isRegister ? (
              <p style={{ fontSize: "0.875rem", color: "var(--text-secondary)" }}>
                Already have an account?{" "}
                <button
                  type="button"
                  className="btn-link"
                  onClick={() => {
                    setIsRegister(false);
                    setError("");
                  }}
                  style={{ color: "var(--accent-primary)", fontWeight: 600, background: "none", border: "none", cursor: "pointer" }}
                >
                  Sign In
                </button>
              </p>
            ) : (
              <p style={{ fontSize: "0.875rem", color: "var(--text-secondary)" }}>
                Don&apos;t have an account yet?{" "}
                <button
                  type="button"
                  className="btn-link"
                  onClick={() => {
                    setIsRegister(true);
                    setError("");
                  }}
                  style={{ color: "var(--accent-primary)", fontWeight: 600, background: "none", border: "none", cursor: "pointer" }}
                >
                  Create Account
                </button>
              </p>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}
