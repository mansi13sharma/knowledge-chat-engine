import { useCallback, useEffect, useState } from "react";
import ChatPage from "./pages/ChatPage";
import AdminPage from "./pages/AdminPage";
import { navigate } from "./router";
import "./App.css";

// Minimal history-API router (no react-router dependency needed for two
// routes): "/" -> the chat widget, "/admin" -> the admin dashboard.
function currentPath() {
  return window.location.pathname === "/admin" ? "/admin" : "/";
}

function App() {
  const [path, setPath] = useState(currentPath());

  useEffect(() => {
    const onPopState = () => setPath(currentPath());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const handleNavClick = useCallback((e, target) => {
    e.preventDefault();
    navigate(target);
    setPath(target);
  }, []);

  return (
    <>
      <nav className="top-nav">
        <a href="/" className={path === "/" ? "active" : ""} onClick={(e) => handleNavClick(e, "/")}>
          Chat
        </a>
        <a href="/admin" className={path === "/admin" ? "active" : ""} onClick={(e) => handleNavClick(e, "/admin")}>
          Admin
        </a>
      </nav>
      {path === "/admin" ? <AdminPage /> : <ChatPage />}
    </>
  );
}

export default App;
