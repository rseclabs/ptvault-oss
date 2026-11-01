/**
 * PTVault API - Unified API Client
 *
 * This is a facade that exports all API modules for backward compatibility.
 * Individual modules can be imported directly from api/* for better tree-shaking.
 *
 * Usage:
 *   // Use the global API object (backward compatible)
 *   await API.hosts.getAll();
 *
 *   // Or import specific modules (recommended for new code)
 *   import { HostsAPI } from './api/hosts.js';
 *   await HostsAPI.getAll();
 */

import { AuthAPI } from './api/auth.js';
import { EngagementsAPI } from './api/engagements.js';
import { EvidenceAPI } from './api/evidence.js';
import { ExportAPI } from './api/export.js';
import { TagsAPI } from './api/tags.js';
import { HostsAPI } from './api/hosts.js';
import { CommandsAPI } from './api/commands.js';
import { AdminAPI } from './api/admin.js';
import { ShellOnelinersAPI } from './api/shelloneliners.js';
import { ReportingAPI } from './api/reporting.js';
import { TestPlansAPI } from './api/testplans.js';
import { FiltersAPI } from './api/filters.js';
import { RelationshipsAPI } from './api/relationships.js';
import { UsersAPI } from './api/users.js';
import { AttackMapsAPI } from './api/attack_maps.js';
import { TeamsAPI } from './api/teams.js';
import { ClientsAPI } from './api/clients.js';
import { DashboardAPI } from './api/dashboard.js';

// Export individual APIs for direct import
export {
    AuthAPI,
    EngagementsAPI,
    EvidenceAPI,
    ExportAPI,
    TagsAPI,
    HostsAPI,
    CommandsAPI,
    AdminAPI,
    ShellOnelinersAPI,
    ReportingAPI,
    TestPlansAPI,
    FiltersAPI,
    RelationshipsAPI,
    UsersAPI,
    AttackMapsAPI,
    TeamsAPI,
    ClientsAPI,
    DashboardAPI
};

// Legacy API object for backward compatibility
const API = {
    auth: AuthAPI,
    engagements: EngagementsAPI,
    evidence: EvidenceAPI,
    export: ExportAPI,
    tags: TagsAPI,
    hosts: HostsAPI,
    commands: CommandsAPI,
    admin: AdminAPI,
    shellOneliners: ShellOnelinersAPI,
    reporting: ReportingAPI,
    testPlans: TestPlansAPI,
    filters: FiltersAPI,
    relationships: RelationshipsAPI,
    users: UsersAPI,
    attackMaps: AttackMapsAPI,
    teams: TeamsAPI,
    clients: ClientsAPI,
    dashboard: DashboardAPI
};

// Make available globally for modules that expect it
window.API = API;

export default API;
