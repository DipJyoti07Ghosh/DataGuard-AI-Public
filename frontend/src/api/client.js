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
};
