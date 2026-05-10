import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './hooks/useAuth'
import ProtectedRoute from './components/ProtectedRoute'
import AdminRoute from './components/AdminRoute'
import AppShell from './components/AppShell'

import AuthPage from './pages/AuthPage'
import AdminSetupPage from './pages/AdminSetupPage'
import DashboardPage from './pages/DashboardPage'
import IngestPage from './pages/IngestPage'
import AccessionPage from './pages/AccessionPage'
import IngestedDataPage from './pages/IngestedDataPage'
import AdminDashboardPage from './pages/AdminDashboardPage'
import TestSessionPage from './pages/TestSessionPage'
import ForgotPassword from './pages/ForgotPassword'
import ResetPasswordPage from './pages/ResetPasswordPage'
import LandingPage from './pages/LandingPage'
import AnalysisReportPage from './pages/AnalysisReportPage'

function Shell({ children }) {
  return (
    <ProtectedRoute>
      <AppShell>{children}</AppShell>
    </ProtectedRoute>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public auth routes */}
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<AuthPage />} />
          <Route path="/signup" element={<AuthPage />} />
          <Route path="/admin/setup" element={<AdminSetupPage />} />
          <Route path="/test-session" element={<TestSessionPage />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />

          {/* Protected user routes */}
          <Route path="/dashboard" element={<Shell><DashboardPage /></Shell>} />
          <Route path="/ingest" element={<Shell><IngestPage /></Shell>} />
          <Route path="/accession" element={<Shell><AccessionPage /></Shell>} />
          <Route path="/ingested-data" element={<Shell><IngestedDataPage /></Shell>} />
          <Route path="/analysis/:jobId" element={<Shell><AnalysisReportPage /></Shell>} />

          {/* Admin-only route */}
          <Route path="/admin" element={
            <AdminRoute>
              <AppShell><AdminDashboardPage /></AppShell>
            </AdminRoute>
          } />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
