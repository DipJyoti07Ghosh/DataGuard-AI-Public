/**
 * DataGuard AI — API Client
 *
 * Centralized HTTP client for communicating with the FastAPI backend.
 * All API calls go through these functions.
 *
 * Authentication:
 *   - JWT is stored in localStorage under 'dataguard_token'
 *   - Every request automatically includes `Authorization: Bearer <token>`
 *   - On 401, the stale token is cleared so the UI can redirect to /login
 */

const API_BASE = '/api';

const TOKEN_KEY = 'dataguard_token';
const USER_KEY = 'dataguard_user';

// ---------------------------------------------------------------------------
// Auth token helpers
// ---------------------------------------------------------------------------
export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function getStoredUser() {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function setAuth(token, user) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

/**
 * Generic fetch wrapper with error handling.
 */
async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const config = {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  };

  // Don't set Content-Type for FormData (browser sets multipart boundary)
  if (options.body instanceof FormData) {
    delete config.headers['Content-Type'];
  }

  // Attach Bearer token if we have one
  const token = getToken();
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`;
  }

  try {
    const response = await fetch(url, config);

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      const error = new Error(
        errorData.detail || `API Error: ${response.status} ${response.statusText}`
      );
      error.status = response.status;
      error.data = errorData;

      // Auto-clear stale token on 401 so AuthContext can react
      if (response.status === 401) {
        clearAuth();
      }

      throw error;
    }

    // Handle empty responses (204 No Content)
    if (response.status === 204) {
      return null;
    }

    return await response.json();
  } catch (err) {
    if (err.status) throw err; // Re-throw API errors
    console.error(`Network error calling ${url}:`, err);
    throw new Error('Unable to connect to the server. Please check if the backend is running.');
  }
}

// ---------------------------------------------------------------------------
// Authentication Endpoints
// ---------------------------------------------------------------------------
export const authApi = {
  register: (name, email, password) =>
    request('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ name, email, password }),
    }),

  login: (email, password) =>
    request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  googleLogin: (idToken) =>
    request('/auth/google', {
      method: 'POST',
      body: JSON.stringify({ id_token: idToken }),
    }),

  me: () => request('/auth/me'),
};

/**
 * Health check — verify backend and database connectivity.
 */
export async function checkHealth() {
  return request('/health');
}

// ---------------------------------------------------------------------------
// Dataset Endpoints (Phase 2 & Phase 3)
// ---------------------------------------------------------------------------

/**
 * Upload a CSV or Excel file for inspection and persistent version tracking.
 * @param {File} file - The file to upload.
 * @param {string} [datasetName] - Optional custom dataset name.
 * @param {string} [description] - Optional dataset description.
 * @returns {Promise<Object>} Upload metadata and version response.
 */
export async function uploadDataset(file, datasetName = '', description = '') {
  const formData = new FormData();
  formData.append('file', file);
  if (datasetName && datasetName.trim()) {
    formData.append('dataset_name', datasetName.trim());
  }
  if (description && description.trim()) {
    formData.append('description', description.trim());
  }

  return request('/datasets/upload', {
    method: 'POST',
    body: formData,
  });
}

/**
 * List all logical datasets in the system with aggregated version info.
 * @returns {Promise<Array>} List of DatasetListItem objects.
 */
export async function getDatasets() {
  return request('/datasets');
}

/**
 * Get detailed dataset metadata and version timeline.
 * @param {string} datasetId - Dataset UUID.
 * @returns {Promise<Object>} Dataset detail with versions.
 */
export async function getDataset(datasetId) {
  return request(`/datasets/${datasetId}`);
}

/**
 * Get metadata for a specific dataset version snapshot.
 * @param {string} datasetId - Dataset UUID.
 * @param {string} versionId - Version UUID.
 * @returns {Promise<Object>} Dataset version detail.
 */
export async function getDatasetVersion(datasetId, versionId) {
  return request(`/datasets/${datasetId}/versions/${versionId}`);
}

/**
 * Delete a dataset and all associated versions.
 * @param {string} datasetId - Dataset UUID.
 * @returns {Promise<Object>} Success message.
 */
export async function deleteDataset(datasetId) {
  return request(`/datasets/${datasetId}`, {
    method: 'DELETE',
  });
}

// ---------------------------------------------------------------------------
// Profiling Endpoints (Phase 4)
// ---------------------------------------------------------------------------

/**
 * Generate (or force recompute) a statistical profile for a dataset version.
 * @param {string} datasetId - Dataset UUID.
 * @param {string} versionId - Version UUID.
 * @param {boolean} [force=false] - Whether to force recomputation.
 * @returns {Promise<Object>} ProfilingResponse object.
 */
export async function generateProfile(datasetId, versionId, force = false) {
  return request(
    `/datasets/${datasetId}/versions/${versionId}/profile?force_recompute=${force}`,
    { method: 'POST' }
  );
}

/**
 * Retrieve cached statistical profile for a dataset version.
 * @param {string} datasetId - Dataset UUID.
 * @param {string} versionId - Version UUID.
 * @returns {Promise<Object>} ProfilingResponse object.
 */
export async function getProfile(datasetId, versionId) {
  return request(`/datasets/${datasetId}/versions/${versionId}/profile`);
}

// ---------------------------------------------------------------------------
// Quality Endpoints (Phase 5)
// ---------------------------------------------------------------------------

/**
 * Run automated quality validation or force recomputation for a dataset version.
 * @param {string} datasetId - Dataset UUID.
 * @param {string} versionId - Version UUID.
 * @param {boolean} [force=false] - Whether to force recompute.
 * @returns {Promise<Object>} QualityResponse object.
 */
export async function generateQuality(datasetId, versionId, force = false) {
  return request(
    `/datasets/${datasetId}/versions/${versionId}/quality?force_recompute=${force}`,
    { method: 'POST' }
  );
}

/**
 * Retrieve latest cached quality scorecard for a dataset version.
 * @param {string} datasetId - Dataset UUID.
 * @param {string} versionId - Version UUID.
 * @returns {Promise<Object>} QualityResponse object.
 */
export async function getQuality(datasetId, versionId) {
  return request(`/datasets/${datasetId}/versions/${versionId}/quality`);
}

/**
 * Retrieve granular expectation rule details with optional filters.
 * @param {string} datasetId - Dataset UUID.
 * @param {string} versionId - Version UUID.
 * @param {Object} [params={}] - Filter params { status_filter, category_filter }.
 * @returns {Promise<Array>} List of ExpectationRuleResult objects.
 */
export async function getQualityDetails(datasetId, versionId, params = {}) {
  const query = new URLSearchParams(params).toString();
  const qs = query ? `?${query}` : '';
  return request(`/datasets/${datasetId}/versions/${versionId}/quality/details${qs}`);
}

// ---------------------------------------------------------------------------
// PII Detection Endpoints (Phase 6)
// ---------------------------------------------------------------------------

/**
 * Trigger an automated PII detection scan for a dataset version.
 * @param {string} datasetId - Dataset UUID.
 * @param {string} versionId - Version UUID.
 * @param {boolean} [force=false] - Whether to force re-scan.
 * @returns {Promise<Object>} PIIScanResultResponse object.
 */
export async function scanPII(datasetId, versionId, force = false) {
  return request(
    `/datasets/${datasetId}/versions/${versionId}/pii/scan?force_recompute=${force}`,
    { method: 'POST' }
  );
}

/**
 * Retrieve cached PII scan results for a dataset version.
 * @param {string} datasetId - Dataset UUID.
 * @param {string} versionId - Version UUID.
 * @returns {Promise<Object>} PIIScanResultResponse object.
 */
export async function getPIIScan(datasetId, versionId) {
  return request(`/datasets/${datasetId}/versions/${versionId}/pii`);
}

/**
 * Retrieve detailed PII findings with optional query filters.
 * @param {string} datasetId - Dataset UUID.
 * @param {string} versionId - Version UUID.
 * @param {Object} [params={}] - Filter params { entity_type, risk_level, column_name }.
 * @returns {Promise<Object>} PIIDetailsResponse object.
 */
export async function getPIIDetails(datasetId, versionId, params = {}) {
  const query = new URLSearchParams(params).toString();
  const qs = query ? `?${query}` : '';
  return request(`/datasets/${datasetId}/versions/${versionId}/pii/details${qs}`);
}

// ---------------------------------------------------------------------------
// ML Column Risk Classification Endpoints (Phase 7)
// ---------------------------------------------------------------------------

/**
 * Trigger ML column classification and risk scoring for a dataset version.
 * @param {string} datasetId - Dataset UUID.
 * @param {string} versionId - Version UUID.
 * @param {boolean} [force=false] - Whether to force re-prediction.
 * @returns {Promise<Object>} DatasetRiskSummaryResponse object.
 */
export async function predictRisk(datasetId, versionId, force = false) {
  return request(
    `/datasets/${datasetId}/versions/${versionId}/risk/predict?force_recompute=${force}`,
    { method: 'POST' }
  );
}

/**
 * Retrieve cached ML column risk predictions for a dataset version.
 * @param {string} datasetId - Dataset UUID.
 * @param {string} versionId - Version UUID.
 * @returns {Promise<Object>} DatasetRiskSummaryResponse object.
 */
export async function getRiskPredictions(datasetId, versionId) {
  return request(`/datasets/${datasetId}/versions/${versionId}/risk`);
}

/**
 * Retrieve detailed column risk predictions with optional query filters.
 * @param {string} datasetId - Dataset UUID.
 * @param {string} versionId - Version UUID.
 * @param {Object} [params={}] - Filter params { risk_level, domain, column_name }.
 * @returns {Promise<Object>} RiskDetailsResponse object.
 */
export async function getRiskDetails(datasetId, versionId, params = {}) {
  const query = new URLSearchParams(params).toString();
  const qs = query ? `?${query}` : '';
  return request(`/datasets/${datasetId}/versions/${versionId}/risk/details${qs}`);
}

// ---------------------------------------------------------------------------
// Anomaly Detection Endpoints (Phase 8)
// ---------------------------------------------------------------------------

/**
 * Trigger anomaly and outlier detection for a dataset version.
 * @param {string} datasetId - Dataset UUID.
 * @param {string} versionId - Version UUID.
 * @param {boolean} [force=false] - Whether to force re-computation.
 * @returns {Promise<Object>} DatasetAnomalySummaryResponse object.
 */
export async function detectAnomalies(datasetId, versionId, force = false) {
  return request(
    `/datasets/${datasetId}/versions/${versionId}/anomalies/detect?force_recompute=${force}`,
    { method: 'POST' }
  );
}

/**
 * Retrieve cached anomaly scorecard for a dataset version.
 * @param {string} datasetId - Dataset UUID.
 * @param {string} versionId - Version UUID.
 * @returns {Promise<Object>} DatasetAnomalySummaryResponse object.
 */
export async function getAnomalies(datasetId, versionId) {
  return request(`/datasets/${datasetId}/versions/${versionId}/anomalies`);
}

/**
 * Retrieve detailed column anomaly findings with optional query filters.
 * @param {string} datasetId - Dataset UUID.
 * @param {string} versionId - Version UUID.
 * @param {Object} [params={}] - Filter params { severity, method, column_name }.
 * @returns {Promise<Object>} AnomalyDetailsResponse object.
 */
export async function getAnomalyDetails(datasetId, versionId, params = {}) {
  const query = new URLSearchParams(params).toString();
  const qs = query ? `?${query}` : '';
  return request(`/datasets/${datasetId}/versions/${versionId}/anomalies/details${qs}`);
}

// ---------------------------------------------------------------------------
// Dataset Health & Issue Prioritization Endpoints (Phase 9)
// ---------------------------------------------------------------------------

/**
 * Trigger dataset health analysis and issue prioritization for a dataset version.
 * @param {string} datasetId - Dataset UUID.
 * @param {string} versionId - Version UUID.
 * @param {boolean} [force=false] - Whether to force recomputation.
 * @returns {Promise<Object>} DatasetHealthSummaryResponse object.
 */
export async function analyzeIssues(datasetId, versionId, force = false) {
  return request(
    `/datasets/${datasetId}/versions/${versionId}/issues/analyze?force_recompute=${force}`,
    { method: 'POST' }
  );
}

/**
 * Retrieve cached dataset health summary for a dataset version.
 * @param {string} datasetId - Dataset UUID.
 * @param {string} versionId - Version UUID.
 * @returns {Promise<Object>} DatasetHealthSummaryResponse object.
 */
export async function getIssuesSummary(datasetId, versionId) {
  return request(`/datasets/${datasetId}/versions/${versionId}/issues/summary`);
}

/**
 * Retrieve prioritized data quality issues with optional query filters.
 * @param {string} datasetId - Dataset UUID.
 * @param {string} versionId - Version UUID.
 * @param {Object} [params={}] - Filter params { severity, source, issue_type, column, min_priority }.
 * @returns {Promise<Object>} IssueListResponse object.
 */
export async function getIssues(datasetId, versionId, params = {}) {
  const query = new URLSearchParams(params).toString();
  const qs = query ? `?${query}` : '';
  return request(`/datasets/${datasetId}/versions/${versionId}/issues${qs}`);
}

/**
 * Retrieve detailed explanation and remediation advice for a single issue.
 * @param {string} datasetId - Dataset UUID.
 * @param {string} versionId - Version UUID.
 * @param {string} issueId - Issue UUID.
 * @returns {Promise<Object>} DataQualityIssueResponse object.
 */
export async function getIssueDetail(datasetId, versionId, issueId) {
  return request(`/datasets/${datasetId}/versions/${versionId}/issues/${issueId}`);
}

// ---------------------------------------------------------------------------
// Comparison & Drift Detection Endpoints (Phase 10)
// ---------------------------------------------------------------------------

/**
 * Compare two snapshot versions of the same dataset.
 * @param {string} datasetId - Dataset UUID.
 * @param {string} baselineVersionId - Reference baseline version UUID.
 * @param {string} currentVersionId - Target current version UUID.
 * @param {boolean} [forceRecompute=false] - Force recompute drift analysis.
 * @returns {Promise<Object>} DatasetComparisonResponse object.
 */
export async function compareDatasetVersions(datasetId, baselineVersionId, currentVersionId, forceRecompute = false) {
  return request(`/datasets/${datasetId}/compare`, {
    method: 'POST',
    body: JSON.stringify({
      baseline_version_id: baselineVersionId,
      current_version_id: currentVersionId,
      force_recompute: forceRecompute,
    }),
  });
}

/**
 * Retrieve an existing dataset comparison by its comparison ID.
 * @param {string} datasetId - Dataset UUID.
 * @param {string} comparisonId - Comparison UUID.
 * @returns {Promise<Object>} DatasetComparisonResponse object.
 */
export async function getDatasetComparison(datasetId, comparisonId) {
  return request(`/datasets/${datasetId}/comparisons/${comparisonId}`);
}

/**
 * List past comparisons for a dataset with optional version filters.
 * @param {string} datasetId - Dataset UUID.
 * @param {string} [baselineVersionId=null] - Optional baseline version UUID.
 * @param {string} [currentVersionId=null] - Optional current version UUID.
 * @returns {Promise<Array>} List of ComparisonListItemResponse objects.
 */
export async function getDatasetComparisons(datasetId, baselineVersionId = null, currentVersionId = null) {
  const params = {};
  if (baselineVersionId) params.baseline_version_id = baselineVersionId;
  if (currentVersionId) params.current_version_id = currentVersionId;
  const query = new URLSearchParams(params).toString();
  const qs = query ? `?${query}` : '';
  return request(`/datasets/${datasetId}/comparisons${qs}`);
}

/**
 * Retrieve single column drift details from a comparison.
 * @param {string} datasetId - Dataset UUID.
 * @param {string} comparisonId - Comparison UUID.
 * @param {string} columnName - Column name.
 * @returns {Promise<Object>} ColumnDriftResponse object.
 */
export async function getColumnDriftDetail(datasetId, comparisonId, columnName) {
  return request(`/datasets/${datasetId}/comparisons/${comparisonId}/columns/${encodeURIComponent(columnName)}`);
}

// ---------------------------------------------------------------------------
// RAG Knowledge & Retrieval Endpoints (Phase 11)
// ---------------------------------------------------------------------------

/**
 * Index stored analytical results for a specific dataset version into RAG.
 * @param {string} datasetId - Dataset UUID.
 * @param {string} versionId - Version UUID.
 * @param {boolean} [forceReindex=false] - Whether to bypass content hash and force re-embedding.
 * @returns {Promise<Object>} RAGIndexResponse object.
 */
export async function indexVersionRAG(datasetId, versionId, forceReindex = false) {
  return request(`/datasets/${datasetId}/versions/${versionId}/rag/index`, {
    method: 'POST',
    body: JSON.stringify({ force_reindex: forceReindex }),
  });
}

/**
 * Index all versions and comparisons for a dataset into RAG.
 * @param {string} datasetId - Dataset UUID.
 * @param {boolean} [forceReindex=false] - Whether to force reindex.
 * @returns {Promise<Object>} RAGIndexResponse object.
 */
export async function indexDatasetRAG(datasetId, forceReindex = false) {
  return request(`/datasets/${datasetId}/rag/index`, {
    method: 'POST',
    body: JSON.stringify({ force_reindex: forceReindex }),
  });
}

/**
 * Index stored version comparison results into RAG.
 * @param {string} datasetId - Dataset UUID.
 * @param {string} comparisonId - Comparison UUID.
 * @param {boolean} [forceReindex=false] - Whether to force reindex.
 * @returns {Promise<Object>} RAGIndexResponse object.
 */
export async function indexComparisonRAG(datasetId, comparisonId, forceReindex = false) {
  return request(`/datasets/${datasetId}/comparisons/${comparisonId}/rag/index`, {
    method: 'POST',
    body: JSON.stringify({ force_reindex: forceReindex }),
  });
}

/**
 * Execute semantic vector search and assemble grounded factual context.
 * @param {string} datasetId - Dataset UUID.
 * @param {Object} retrieveRequest - { query, scope, version_id, comparison_id, top_k, phases, include_comparisons }
 * @returns {Promise<Object>} GroundedContextResponse object.
 */
export async function retrieveRAG(datasetId, retrieveRequest) {
  return request(`/datasets/${datasetId}/rag/retrieve`, {
    method: 'POST',
    body: JSON.stringify(retrieveRequest),
  });
}

/**
 * List indexed RAG documents for a dataset.
 * @param {string} datasetId - Dataset UUID.
 * @param {Object} [params={}] - Optional query params (version_id, source_phase, document_type).
 * @returns {Promise<Object>} RAGDocumentListResponse.
 */
export async function getRAGDocuments(datasetId, params = {}) {
  const query = new URLSearchParams();
  if (params.version_id) query.append('version_id', params.version_id);
  if (params.source_phase) query.append('source_phase', params.source_phase);
  if (params.document_type) query.append('document_type', params.document_type);
  const qStr = query.toString() ? `?${query.toString()}` : '';
  return request(`/datasets/${datasetId}/rag/documents${qStr}`);
}

/**
 * List indexed RAG documents for a specific version.
 * @param {string} datasetId - Dataset UUID.
 * @param {string} versionId - Version UUID.
 * @param {Object} [params={}] - Optional query params (source_phase).
 * @returns {Promise<Object>} RAGDocumentListResponse.
 */
export async function getVersionRAGDocuments(datasetId, versionId, params = {}) {
  const query = new URLSearchParams();
  if (params.source_phase) query.append('source_phase', params.source_phase);
  const qStr = query.toString() ? `?${query.toString()}` : '';
  return request(`/datasets/${datasetId}/versions/${versionId}/rag/documents${qStr}`);
}

/**
 * Purge RAG documents for a dataset.
 * @param {string} datasetId - Dataset UUID.
 */
export async function purgeRAGDocuments(datasetId) {
  return request(`/datasets/${datasetId}/rag/documents`, { method: 'DELETE' });
}

// ---------------------------------------------------------------------------
// AI Assistant Endpoints (Phase 12)
// ---------------------------------------------------------------------------

/**
 * Ask the AI Assistant a grounded analytical question.
 * @param {string} datasetId - Dataset UUID.
 * @param {Object} askRequest - { question, scope, version_id, comparison_id, top_k, phases, min_similarity }
 * @returns {Promise<Object>} AssistantAskResponse object.
 */
export async function askAssistant(datasetId, askRequest) {
  return request(`/datasets/${datasetId}/assistant/ask`, {
    method: 'POST',
    body: JSON.stringify(askRequest),
  });
}

export async function getAssistantHealth() {
  return request(`/assistant/health`);
}

/**
 * Get aggregated dashboard overview metrics for a dataset version.
 * @param {string} datasetId - Dataset UUID.
 * @param {string} [versionId] - Optional Dataset Version UUID.
 * @returns {Promise<Object>} DashboardResponse object.
 */
export async function getDashboard(datasetId, versionId = null) {
  if (versionId) {
    return request(`/datasets/${datasetId}/versions/${versionId}/dashboard`);
  }
  return request(`/datasets/${datasetId}/dashboard`);
}


// ---------------------------------------------------------------------------
// Chat & Conversational Intelligence Endpoints (Phase 14)
// ---------------------------------------------------------------------------

/**
 * Create a new persistent chat session scoped to dataset, version, or comparison.
 * @param {string} datasetId - Dataset UUID
 * @param {Object} sessionData - { scope, version_id, comparison_id, title }
 * @returns {Promise<Object>} Created ChatSessionResponse
 */
export async function createChatSession(datasetId, sessionData = {}) {
  return request(`/datasets/${datasetId}/chat/sessions`, {
    method: 'POST',
    body: JSON.stringify(sessionData),
  });
}

/**
 * List all chat sessions for a dataset.
 * @param {string} datasetId - Dataset UUID
 * @returns {Promise<Array>} List of ChatSessionResponse objects
 */
export async function getChatSessions(datasetId) {
  return request(`/datasets/${datasetId}/chat/sessions`);
}

/**
 * Get chat session details with full chronological message history.
 * @param {string} datasetId - Dataset UUID
 * @param {string} sessionId - Chat session UUID
 * @returns {Promise<Object>} ChatSessionDetailResponse
 */
export async function getChatSession(datasetId, sessionId) {
  return request(`/datasets/${datasetId}/chat/sessions/${sessionId}`);
}

/**
 * Update chat session title.
 * @param {string} datasetId - Dataset UUID
 * @param {string} sessionId - Chat session UUID
 * @param {Object} updateData - { title }
 * @returns {Promise<Object>} Updated ChatSessionResponse
 */
export async function updateChatSession(datasetId, sessionId, updateData) {
  return request(`/datasets/${datasetId}/chat/sessions/${sessionId}`, {
    method: 'PATCH',
    body: JSON.stringify(updateData),
  });
}

/**
 * Delete a chat session and cascade delete all child messages.
 * @param {string} datasetId - Dataset UUID
 * @param {string} sessionId - Chat session UUID
 * @returns {Promise<null>}
 */
export async function deleteChatSession(datasetId, sessionId) {
  return request(`/datasets/${datasetId}/chat/sessions/${sessionId}`, {
    method: 'DELETE',
  });
}

/**
 * Send a user message in a chat session and get a grounded assistant response.
 * @param {string} datasetId - Dataset UUID
 * @param {string} sessionId - Chat session UUID
 * @param {string} content - User prompt text (max 8000 chars)
 * @returns {Promise<Object>} ChatMessageResponse
 */
export async function sendChatMessage(datasetId, sessionId, content) {
  return request(`/datasets/${datasetId}/chat/sessions/${sessionId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ content }),
  });
}

/**
 * Retry generation for the latest user message without duplicating the user message.
 * @param {string} datasetId - Dataset UUID
 * @param {string} sessionId - Chat session UUID
 * @returns {Promise<Object>} ChatMessageResponse
 */
export async function retryChatMessage(datasetId, sessionId) {
  return request(`/datasets/${datasetId}/chat/sessions/${sessionId}/retry`, {
    method: 'POST',
  });
}

export default {
  checkHealth,
  uploadDataset,
  getDatasets,
  getDataset,
  getDatasetVersion,
  deleteDataset,
  generateProfile,
  getProfile,
  generateQuality,
  getQuality,
  getQualityDetails,
  scanPII,
  getPIIScan,
  getPIIDetails,
  predictRisk,
  getRiskPredictions,
  getRiskDetails,
  detectAnomalies,
  getAnomalies,
  getAnomalyDetails,
  analyzeIssues,
  getIssuesSummary,
  getIssues,
  getIssueDetail,
  compareDatasetVersions,
  getDatasetComparison,
  getDatasetComparisons,
  getColumnDriftDetail,
  indexVersionRAG,
  indexDatasetRAG,
  indexComparisonRAG,
  retrieveRAG,
  getRAGDocuments,
  getVersionRAGDocuments,
  purgeRAGDocuments,
  askAssistant,
  getAssistantHealth,
  getDashboard,
  createChatSession,
  getChatSessions,
  getChatSession,
  updateChatSession,
  deleteChatSession,
  sendChatMessage,
  retryChatMessage,

  // Auth
  authApi,
  getToken,
  getStoredUser,
  setAuth,
  clearAuth,
};







