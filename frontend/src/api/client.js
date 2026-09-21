/**
 * DataGuard AI — API Client
 *
 * Centralized HTTP client for communicating with the FastAPI backend.
 * All API calls go through these functions.
 */

const API_BASE = '/api';

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

  try {
    const response = await fetch(url, config);

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      const error = new Error(
        errorData.detail || `API Error: ${response.status} ${response.statusText}`
      );
      error.status = response.status;
      error.data = errorData;
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
};




