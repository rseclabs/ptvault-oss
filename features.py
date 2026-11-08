"""Blueprint registry for PTVault.

Centralizes blueprint registration so app.py and the PyInstaller spec share
one list of route modules.
"""

import importlib
import logging

logger = logging.getLogger(__name__)

BLUEPRINTS = [
    ('routes.auth', 'auth_bp'),
    ('routes.dashboard', 'dashboard_bp'),
    ('routes.engagements', 'engagements_bp'),
    ('routes.evidence', 'evidence_bp'),
    ('routes.tags', 'tags_bp'),
    ('routes.hosts', 'hosts_bp'),
    ('routes.commands', 'commands_bp'),
    ('routes.admin', 'admin_bp'),
    ('routes.shell_oneliners', 'shell_oneliners_bp'),
    ('routes.filters', 'filters_bp'),
    ('routes.users', 'users_bp'),
    ('routes.teams', 'teams_bp'),
    ('routes.clients', 'clients_bp'),
    ('routes.test', 'test_bp'),
    ('routes.reporting', 'reporting_bp'),
    ('routes.testplans', 'testplans_bp'),
    ('routes.engagement_members', 'engagement_members_bp'),
    ('routes.relationships', 'relationships_bp'),
    ('routes.attack_maps', 'attack_maps_bp'),
    ('routes.templates', 'templates_bp'),
]


def register_blueprints(app):
    """Register all blueprints with the Flask app.

    Returns:
        int: Number of blueprints successfully registered
    """
    registered = 0
    for module_path, bp_name in BLUEPRINTS:
        try:
            module = importlib.import_module(module_path)
            app.register_blueprint(getattr(module, bp_name))
            registered += 1
        except Exception as e:
            logger.error("Failed to register blueprint %s.%s: %s", module_path, bp_name, e)

    # Every successful mutating API call is audited (L-9)
    from utils.audit_logger import audit_mutation
    app.after_request(audit_mutation)

    logger.info("Registered %d blueprints", registered)
    return registered
