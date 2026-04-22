import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { FolderImportPage } from "./pages/FolderImportPage";
import { KnowledgeItemDetailPage } from "./pages/KnowledgeItemDetailPage";
import { ReviewListPage } from "./pages/ReviewListPage";

export default function App() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <h1>SAP Knowledge Database</h1>
        <nav className="app-nav">
          <NavLink to="/import" className={({ isActive }) => (isActive ? "app-nav__link app-nav__link--active" : "app-nav__link")}>
            Import
          </NavLink>
          <NavLink to="/review" className={({ isActive }) => (isActive ? "app-nav__link app-nav__link--active" : "app-nav__link")}>
            Review
          </NavLink>
        </nav>
      </header>
      <div className="app-main">
        <Routes>
          <Route path="/" element={<Navigate to="/import" replace />} />
          <Route path="/import" element={<FolderImportPage />} />
          <Route path="/review" element={<ReviewListPage />} />
          <Route path="/knowledge-items/:itemId" element={<KnowledgeItemDetailPage />} />
        </Routes>
      </div>
    </div>
  );
}
