/**
 * Attack Maps API
 *
 * Handles attack map CRUD, node/edge management, and SVG export.
 */
import { apiRequest } from '../lib/request.js';

export const AttackMapsAPI = {
    // ── Maps ────────────────────────────────────────────────

    async list() {
        const response = await apiRequest.get('/attack-maps');
        return response.maps || [];
    },

    async create(data) {
        return apiRequest.post('/attack-maps', data);
    },

    async get(mapId) {
        return apiRequest.get(`/attack-maps/${mapId}`);
    },

    async update(mapId, data) {
        return apiRequest.put(`/attack-maps/${mapId}`, data);
    },

    async remove(mapId) {
        return apiRequest.delete(`/attack-maps/${mapId}`);
    },

    async duplicate(mapId) {
        return apiRequest.post(`/attack-maps/${mapId}/duplicate`, {});
    },

    // ── Nodes ───────────────────────────────────────────────

    async createNode(mapId, data) {
        return apiRequest.post(`/attack-maps/${mapId}/nodes`, data);
    },

    async updateNode(mapId, nodeId, data) {
        return apiRequest.put(`/attack-maps/${mapId}/nodes/${nodeId}`, data);
    },

    async deleteNode(mapId, nodeId) {
        return apiRequest.delete(`/attack-maps/${mapId}/nodes/${nodeId}`);
    },

    async batchUpdateNodes(mapId, updates) {
        return apiRequest.put(`/attack-maps/${mapId}/nodes/batch`, { updates });
    },

    // ── Edges ───────────────────────────────────────────────

    async createEdge(mapId, data) {
        return apiRequest.post(`/attack-maps/${mapId}/edges`, data);
    },

    async deleteEdge(mapId, edgeId) {
        return apiRequest.delete(`/attack-maps/${mapId}/edges/${edgeId}`);
    },

    // ── Export ──────────────────────────────────────────────

    async getSvg(mapId) {
        return apiRequest.get(`/attack-maps/${mapId}/svg`);
    }
};
