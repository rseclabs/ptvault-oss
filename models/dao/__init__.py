"""Data Access Object (DAO) layer for PTVault.

This package provides a centralized data access layer that consolidates
all SQL queries from route files into reusable, testable, and maintainable
DAO classes.

Usage:
    from models.dao import EngagementDAO, EvidenceDAO, HostDAO

    engagement_dao = EngagementDAO()
    engagements = engagement_dao.find_all()
"""

from models.dao.base import BaseDAO
from models.dao.client_dao import ClientDAO
from models.dao.engagement_dao import EngagementDAO
from models.dao.evidence_dao import EvidenceDAO
from models.dao.host_dao import HostDAO
from models.dao.report_dao import ReportDAO
from models.dao.test_plan_dao import TestPlanDAO
from models.dao.user_dao import UserDAO
from models.dao.relationship_dao import RelationshipDAO, AttackPathDAO
from models.dao.attack_map_dao import AttackMapDAO, AttackMapNodeDAO, AttackMapEdgeDAO
from models.dao.note_tree_dao import NoteTreeDAO

__all__ = [
    'BaseDAO',
    'ClientDAO',
    'EngagementDAO',
    'EvidenceDAO',
    'HostDAO',
    'ReportDAO',
    'TestPlanDAO',
    'UserDAO',
    'RelationshipDAO',
    'AttackPathDAO',
    'AttackMapDAO',
    'AttackMapNodeDAO',
    'AttackMapEdgeDAO',
    'NoteTreeDAO',
]
