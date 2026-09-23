/**
 * DataGuard AI — Root Application Component
 *
 * Sets up React Router with main layout and page routes.
 */

import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import ProtectedRoute from "./components/Auth/ProtectedRoute";
import Login from "./pages/Auth/Login";
import Register from "./pages/Auth/Register";
import MainLayout from "./components/Layout/MainLayout";
import Home from "./pages/Home";
import Dashboard from "./pages/Dashboard";
import Upload from "./pages/Upload";
import Datasets from "./pages/Datasets";
import Profiling from "./pages/Profiling";
import Quality from "./pages/Quality";
import PII from "./pages/PII";
import Risk from "./pages/Risk";
import Anomalies from "./pages/Anomalies";
import Issues from "./pages/Issues";
import Compare from "./pages/Compare";
import RAGExplorer from "./pages/RAGExplorer";
import Assistant from "./pages/Assistant";
import Chat from "./pages/Chat";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public Landing / Home Page */}
          <Route path="/" element={<Home />} />

          {/* Auth Routes */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />

          {/* Core Platform Routes within Main Layout */}
          <Route element={<MainLayout />}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route
              path="/datasets/:datasetId/dashboard"
              element={<Dashboard />}
            />
            <Route
              path="/datasets/:datasetId/versions/:versionId/dashboard"
              element={<Dashboard />}
            />

            <Route
              path="/upload"
              element={
                <ProtectedRoute reason="upload_requires_signin">
                  <Upload />
                </ProtectedRoute>
              }
            />

            <Route path="/datasets" element={<Datasets />} />

            <Route
              path="/datasets/:datasetId/versions/:versionId/profile"
              element={
                <ProtectedRoute reason="signin_required">
                  <Profiling />
                </ProtectedRoute>
              }
            />
            <Route
              path="/datasets/:datasetId/versions/:versionId/quality"
              element={
                <ProtectedRoute reason="signin_required">
                  <Quality />
                </ProtectedRoute>
              }
            />
            <Route
              path="/datasets/:datasetId/versions/:versionId/pii"
              element={
                <ProtectedRoute reason="signin_required">
                  <PII />
                </ProtectedRoute>
              }
            />
            <Route
              path="/datasets/:datasetId/versions/:versionId/risk"
              element={
                <ProtectedRoute reason="signin_required">
                  <Risk />
                </ProtectedRoute>
              }
            />
            <Route
              path="/datasets/:datasetId/versions/:versionId/anomalies"
              element={
                <ProtectedRoute reason="signin_required">
                  <Anomalies />
                </ProtectedRoute>
              }
            />
            <Route
              path="/datasets/:datasetId/versions/:versionId/issues"
              element={
                <ProtectedRoute reason="signin_required">
                  <Issues />
                </ProtectedRoute>
              }
            />

            <Route
              path="/datasets/:datasetId/compare"
              element={
                <ProtectedRoute reason="signin_required">
                  <Compare />
                </ProtectedRoute>
              }
            />
            <Route
              path="/datasets/:datasetId/versions/:versionId/compare"
              element={
                <ProtectedRoute reason="signin_required">
                  <Compare />
                </ProtectedRoute>
              }
            />

            <Route
              path="/rag"
              element={
                <ProtectedRoute reason="signin_required">
                  <RAGExplorer />
                </ProtectedRoute>
              }
            />
            <Route
              path="/datasets/:datasetId/rag"
              element={
                <ProtectedRoute reason="signin_required">
                  <RAGExplorer />
                </ProtectedRoute>
              }
            />
            <Route
              path="/datasets/:datasetId/versions/:versionId/rag"
              element={
                <ProtectedRoute reason="signin_required">
                  <RAGExplorer />
                </ProtectedRoute>
              }
            />

            <Route
              path="/assistant"
              element={
                <ProtectedRoute reason="signin_required">
                  <Assistant />
                </ProtectedRoute>
              }
            />
            <Route
              path="/datasets/:datasetId/assistant"
              element={
                <ProtectedRoute reason="signin_required">
                  <Assistant />
                </ProtectedRoute>
              }
            />
            <Route
              path="/datasets/:datasetId/versions/:versionId/assistant"
              element={
                <ProtectedRoute reason="signin_required">
                  <Assistant />
                </ProtectedRoute>
              }
            />

            <Route
              path="/chat"
              element={
                <ProtectedRoute reason="signin_required">
                  <Chat />
                </ProtectedRoute>
              }
            />
            <Route
              path="/datasets/:datasetId/chat"
              element={
                <ProtectedRoute reason="signin_required">
                  <Chat />
                </ProtectedRoute>
              }
            />
            <Route
              path="/datasets/:datasetId/versions/:versionId/chat"
              element={
                <ProtectedRoute reason="signin_required">
                  <Chat />
                </ProtectedRoute>
              }
            />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
