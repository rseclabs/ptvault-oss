"""Client management routes for PTVault.

Clients are managed in the Admin panel. Full CRUD is admin-only; the
lightweight /options endpoint is open to any authenticated user so the
engagement-create modal can populate its dropdown.
"""

import logging

from flask import Blueprint, request, jsonify, g

from middleware.auth import require_auth, require_role
from models.dao.client_dao import ClientDAO
from utils.audit_logger import audit_create, audit_update
from utils.error_handler import (
    handle_errors,
    ValidationError,
    NotFoundError,
    ConflictError,
    validate_max_length,
)

logger = logging.getLogger(__name__)

clients_bp = Blueprint('clients', __name__, url_prefix='/api/clients')
client_dao = ClientDAO()


# Fields that can be set on create or update.
EDITABLE_FIELDS = (
    'admin_contact_name',
    'admin_contact_email',
    'admin_contact_phone',
    'technical_contact_name',
    'technical_contact_email',
    'technical_contact_phone',
    'address',
    'website',
    'notes',
)


def _extract_payload(data, *, include_name=True):
    """Pick editable fields from request JSON, trimming strings."""
    payload = {}
    if include_name:
        name = (data.get('name') or '').strip()
        if not name:
            raise ValidationError("name is required")
        validate_max_length(name, 200, 'name')
        payload['name'] = name

    for field in EDITABLE_FIELDS:
        if field in data:
            value = data.get(field)
            if isinstance(value, str):
                value = value.strip() or None
            payload[field] = value
    return payload


@clients_bp.route('/options', methods=['GET'])
@require_auth
@handle_errors
def list_client_options():
    """Lightweight id+name listing for dropdowns. Available to any auth user."""
    return jsonify({"clients": client_dao.list_options()}), 200


@clients_bp.route('', methods=['GET'])
@require_auth
@require_role('admin')
@handle_errors
def list_clients():
    """List all clients with full detail (admin only)."""
    clients = client_dao.find_all(order_by='name')
    return jsonify({"clients": clients}), 200


@clients_bp.route('/<int:client_id>', methods=['GET'])
@require_auth
@require_role('admin')
@handle_errors
def get_client(client_id):
    """Get a single client by id (admin only)."""
    client = client_dao.find_by_id(client_id)
    if not client:
        raise NotFoundError("Client not found")
    return jsonify(client), 200


@clients_bp.route('', methods=['POST'])
@require_auth
@require_role('admin')
@handle_errors
def create_client():
    """Create a new client (admin only)."""
    data = request.get_json() or {}
    payload = _extract_payload(data, include_name=True)

    if client_dao.find_by_name(payload['name']):
        raise ConflictError(f"Client '{payload['name']}' already exists")

    payload['created_by'] = g.current_user
    new_id = client_dao.create(payload)

    logger.info("Client created: %s (id=%s) by user %s",
                payload['name'], new_id, g.current_user)
    audit_create('client', new_id, name=payload['name'])

    created = client_dao.find_by_id(new_id)
    return jsonify(created), 201


@clients_bp.route('/<int:client_id>', methods=['PUT'])
@require_auth
@require_role('admin')
@handle_errors
def update_client(client_id):
    """Update an existing client (admin only)."""
    existing = client_dao.find_by_id(client_id)
    if not existing:
        raise NotFoundError("Client not found")

    data = request.get_json() or {}
    payload = _extract_payload(data, include_name='name' in data)

    if 'name' in payload and payload['name'].lower() != (existing['name'] or '').lower():
        clash = client_dao.find_by_name(payload['name'])
        if clash and clash['id'] != client_id:
            raise ConflictError(f"Client '{payload['name']}' already exists")

    if not payload:
        raise ValidationError("No fields to update")

    client_dao.update(client_id, payload)

    logger.info("Client updated: %s by user %s", client_id, g.current_user)
    audit_update('client', client_id, updated_by=g.current_user)

    return jsonify(client_dao.find_by_id(client_id)), 200


@clients_bp.route('/<int:client_id>', methods=['DELETE'])
@require_auth
@require_role('admin')
@handle_errors
def delete_client(client_id):
    """Delete a client (admin only).

    Blocked when engagements still reference this client. The error body
    includes the engagement count so the UI can prompt the admin to
    reassign or remove those engagements first.
    """
    existing = client_dao.find_by_id(client_id)
    if not existing:
        raise NotFoundError("Client not found")

    in_use = client_dao.count_engagements(client_id)
    if in_use > 0:
        return (
            jsonify({
                "error": (
                    f"Client '{existing['name']}' has {in_use} engagement(s). "
                    "Reassign or delete those engagements first."
                ),
                "engagement_count": in_use,
            }),
            409,
        )

    client_dao.delete(client_id)

    logger.info("Client deleted: %s (%s) by user %s",
                client_id, existing['name'], g.current_user)
    audit_update('client', client_id, action='delete',
                 deleted_by=g.current_user, name=existing['name'])

    return jsonify({"status": "deleted"}), 200
