import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from './contexts/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Layout } from './components/Layout';
import { Login } from './pages/Login';
import { Dashboards } from './pages/Dashboards';
import { Allocations } from './pages/Allocations';
import { Activity } from './pages/ActivityNew';
import { Strategies } from './pages/Strategies';
import { StrategyApproval } from './pages/StrategyApproval';
import { Accounts } from './pages/Accounts';
import FundSetup from './pages/FundSetup';
import RawDataViewer from './pages/RawDataViewer';

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 30000, // 30 seconds
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Public routes */}
            <Route path="/login" element={<Login />} />

            {/* Standalone routes (outside Layout) */}
            <Route path="/raw-data/:submissionId" element={<RawDataViewer />} />

            {/* Protected routes */}
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <Layout />
                </ProtectedRoute>
              }
            >
              <Route index element={<Navigate to="/dashboard" replace />} />
              <Route path="dashboard" element={<Dashboards />} />
              <Route path="allocations" element={<Allocations />} />
              <Route path="activity" element={<Activity />} />
              <Route path="strategies" element={<Strategies />} />
              <Route path="strategy-approval" element={<StrategyApproval />} />
              <Route path="accounts" element={<Accounts />} />
              <Route path="hedged-funds" element={<FundSetup />} />
            </Route>

            {/* Catch all - redirect to dashboard */}
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
