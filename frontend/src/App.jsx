/**
 * DataGuard AI — Root Application Component
 *
 * Sets up React Router with main layout and page routes.
 */

import { BrowserRouter, Routes, Route } from 'react-router-dom';
import MainLayout from './components/Layout/MainLayout';
import Dashboard from './pages/Dashboard';
import Upload from './pages/Upload';
import Datasets from './pages/Datasets';
import Profiling from './pages/Profiling';
import Quality from './pages/Quality';
import PII from './pages/PII';
import Risk from './pages/Risk';
import Anomalies from './pages/Anomalies';
import Issues from './pages/Issues';
import Compare from './pages/Compare';
import RAGExplorer from './pages/RAGExplorer';
import Assistant from './pages/Assistant';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<MainLayout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/upload" element={<Upload />} />
          <Route path="/datasets" element={<Datasets />} />
          <Route path="/datasets/:datasetId/versions/:versionId/profile" element={<Profiling />} />
          <Route path="/datasets/:datasetId/versions/:versionId/quality" element={<Quality />} />
          <Route path="/datasets/:datasetId/versions/:versionId/pii" element={<PII />} />
          <Route path="/datasets/:datasetId/versions/:versionId/risk" element={<Risk />} />
          <Route path="/datasets/:datasetId/versions/:versionId/anomalies" element={<Anomalies />} />
          <Route path="/datasets/:datasetId/versions/:versionId/issues" element={<Issues />} />
          <Route path="/datasets/:datasetId/compare" element={<Compare />} />
          <Route path="/datasets/:datasetId/versions/:versionId/compare" element={<Compare />} />
          <Route path="/rag" element={<RAGExplorer />} />
          <Route path="/datasets/:datasetId/rag" element={<RAGExplorer />} />
          <Route path="/datasets/:datasetId/versions/:versionId/rag" element={<RAGExplorer />} />
          <Route path="/assistant" element={<Assistant />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

