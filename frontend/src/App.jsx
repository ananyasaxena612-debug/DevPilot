import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import { ThemeProvider } from "./context/ThemeContext";
import { AuthProvider } from "./context/AuthContext";
import Navbar from "./components/Navbar";
import Footer from "./components/Footer";
import ScrollToTop from "./components/ScrollToTop";
import Home from "./pages/Home";
import MyServers from "./pages/MyServers";
import AddServer from "./pages/AddServer";
import SystemMonitoring from "./pages/SystemMonitoring";
import DockerMonitoring from "./pages/DockerMonitoring";
import LogAnalysis from "./pages/LogAnalysis";
import IncidentTimeMachine from "./pages/IncidentTimeMachine";
import "./App.css";

export default function App() {
  return (
    <Router>
      <ThemeProvider>
        <AuthProvider>
          <ScrollToTop />
          <div className="devpilot-layout">
            <Navbar />
            <main className="devpilot-main" id="main-content">
              <Routes>
                <Route path="/" element={<Home />} />
                <Route path="/servers" element={<MyServers />} />
                <Route path="/servers/add" element={<AddServer />} />
                <Route path="/monitoring" element={<SystemMonitoring />} />
                <Route path="/docker" element={<DockerMonitoring />} />
                <Route path="/analyze" element={<LogAnalysis />} />
                <Route path="/incidents" element={<IncidentTimeMachine />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </main>
            <Footer />
          </div>
        </AuthProvider>
      </ThemeProvider>
    </Router>
  );
}
