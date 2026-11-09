import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import { ThemeProvider } from "./context/ThemeContext";
import Navbar from "./components/Navbar";
import Footer from "./components/Footer";
import ScrollToTop from "./components/ScrollToTop";
import Home from "./pages/Home";
import SystemMonitoring from "./pages/SystemMonitoring";
import DockerMonitoring from "./pages/DockerMonitoring";
import LogAnalysis from "./pages/LogAnalysis";
import IncidentTimeMachine from "./pages/IncidentTimeMachine";
import "./App.css";

export default function App() {
  return (
    <Router>
      <ThemeProvider>
        <ScrollToTop />
        <div className="devpilot-layout">
          <Navbar />
          <main className="devpilot-main" id="main-content">
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/monitoring" element={<SystemMonitoring />} />
              <Route path="/docker" element={<DockerMonitoring />} />
              <Route path="/analyze" element={<LogAnalysis />} />
              <Route path="/incidents" element={<IncidentTimeMachine />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
          <Footer />
        </div>
      </ThemeProvider>
    </Router>
  );
}
