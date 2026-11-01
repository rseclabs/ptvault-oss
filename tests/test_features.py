"""Blueprint registry tests.

PTVault used to split features into Core and Pro tiers. Everything is now
open source, so every blueprint must register and no license endpoints or
license gating modules may remain.
"""

import importlib

import pytest
from flask import Flask

from features import BLUEPRINTS, register_blueprints

FORMERLY_PRO = [
    'reporting_bp',
    'testplans_bp',
    'engagement_members_bp',
    'relationships_bp',
    'attack_maps_bp',
    'templates_bp',
]


@pytest.fixture(scope='module')
def app():
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.registered_count = register_blueprints(app)
    return app


def test_every_blueprint_registers(app):
    assert app.registered_count == len(BLUEPRINTS)


@pytest.mark.parametrize('bp_name', FORMERLY_PRO)
def test_formerly_pro_blueprints_are_registered(bp_name):
    assert any(name == bp_name for _, name in BLUEPRINTS)


def test_formerly_pro_routes_are_mounted(app):
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    for prefix in ('/api/reporting', '/api/testplans', '/api/attack-maps', '/api/relationships'):
        assert any(r.startswith(prefix) for r in rules), f'no routes under {prefix}'


def test_license_endpoints_removed(app):
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert '/api/admin/license' not in rules
    assert '/api/license-status' not in rules


@pytest.mark.parametrize('module', ['models.license', 'middleware.license', 'license_config'])
def test_license_modules_removed(module):
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module)
