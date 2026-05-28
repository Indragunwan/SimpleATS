import "@/App.css";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider } from "@/context/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import Layout from "@/components/Layout";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import Jobs from "@/pages/Jobs";
import JobDetail from "@/pages/JobDetail";
import ScreeningDetail from "@/pages/ScreeningDetail";
import AdminProvider from "@/pages/AdminProvider";
import AdminUsers from "@/pages/AdminUsers";
import TalentPool from "@/pages/TalentPool";
import TalentPoolDetail from "@/pages/TalentPoolDetail";

function Protected({ children, roles }) {
  return (
    <ProtectedRoute allowedRoles={roles}>
      <Layout>{children}</Layout>
    </ProtectedRoute>
  );
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Toaster position="top-right" richColors />
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/login" element={<Login />} />
          <Route
            path="/dashboard"
            element={
              <Protected>
                <Dashboard />
              </Protected>
            }
          />
          <Route
            path="/jobs"
            element={
              <Protected>
                <Jobs />
              </Protected>
            }
          />
          <Route
            path="/jobs/:id"
            element={
              <Protected>
                <JobDetail />
              </Protected>
            }
          />
          <Route
            path="/screenings/:id"
            element={
              <Protected>
                <ScreeningDetail />
              </Protected>
            }
          />
          <Route
            path="/talent-pool"
            element={
              <Protected>
                <TalentPool />
              </Protected>
            }
          />
          <Route
            path="/talent-pool/:id"
            element={
              <Protected>
                <TalentPoolDetail />
              </Protected>
            }
          />
          <Route
            path="/admin/provider"
            element={
              <Protected roles={["admin_it"]}>
                <AdminProvider />
              </Protected>
            }
          />
          <Route
            path="/admin/users"
            element={
              <Protected roles={["admin_it"]}>
                <AdminUsers />
              </Protected>
            }
          />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
