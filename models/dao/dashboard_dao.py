"""DashboardDAO — read-only metric aggregation for the active engagement.

Each method runs one focused query and returns plain Python data structures
ready to be serialized to JSON. The DAO is engagement-scoped, but methods
take engagement_id explicitly so the caller (route) controls scoping.
"""

import json
import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from models.dao.base import BaseDAO

logger = logging.getLogger(__name__)


class DashboardDAO(BaseDAO):
    """Aggregates dashboard metrics for a single engagement."""

    def __init__(self):
        super().__init__(table_name='engagements', engagement_scoped=False)

    def get_kpis(self, engagement_id: int) -> Dict[str, Any]:
        """Return the six headline KPI counts for the engagement."""
        cursor = self.db.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM hosts WHERE engagement_id = ?",
            (engagement_id,),
        )
        hosts = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM host_ports hp "
            "JOIN hosts h ON h.id = hp.host_id "
            "WHERE h.engagement_id = ? AND hp.state = 'open'",
            (engagement_id,),
        )
        open_ports = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM engagement_findings WHERE engagement_id = ?",
            (engagement_id,),
        )
        findings = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM host_credentials hc "
            "JOIN hosts h ON h.id = hc.host_id "
            "WHERE h.engagement_id = ?",
            (engagement_id,),
        )
        credentials = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM hosts "
            "WHERE engagement_id = ? AND (rooted = 1 OR shell = 1)",
            (engagement_id,),
        )
        compromised = cursor.fetchone()[0]

        cursor.execute(
            "SELECT end_date FROM engagements WHERE id = ?",
            (engagement_id,),
        )
        row = cursor.fetchone()
        days_remaining: Optional[int] = None
        if row and row[0]:
            try:
                end = datetime.strptime(row[0], '%Y-%m-%d').date()
                days_remaining = max(0, (end - date.today()).days)
            except ValueError:
                logger.warning(
                    "Bad end_date format for engagement %d: %r",
                    engagement_id,
                    row[0],
                )

        return {
            'hosts': hosts,
            'open_ports': open_ports,
            'findings': findings,
            'credentials': credentials,
            'compromised_hosts': compromised,
            'days_remaining': days_remaining,
        }

    def get_severity_breakdown(self, engagement_id: int) -> List[Dict[str, Any]]:
        """Return [{label, count}] for finding criticalities. Unknown→'info'."""
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT LOWER(COALESCE(NULLIF(criticality, ''), 'info')) AS label, "
            "COUNT(*) AS n FROM engagement_findings "
            "WHERE engagement_id = ? "
            "GROUP BY LOWER(COALESCE(NULLIF(criticality, ''), 'info'))",
            (engagement_id,),
        )
        return [{'label': r[0], 'count': r[1]} for r in cursor.fetchall()]

    def get_top_ports(self, engagement_id: int, limit: int = 15) -> List[Dict[str, Any]]:
        """Top N open ports by host count, with the most-common service per port.

        Ports are collapsed across protocols (a host with TCP/53 and UDP/53
        contributes once to port 53). Each result dict contains:
            - 'port': int
            - 'host_count': int — distinct hosts with that port open
            - 'service': str | None — most common non-empty service name
              across hosts; None if every host's service is NULL/empty.

        Service tie-breaking is deterministic (highest count, then service
        name ASC).
        """
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT hp.port, COUNT(DISTINCT hp.host_id) AS host_count "
            "FROM host_ports hp JOIN hosts h ON h.id = hp.host_id "
            "WHERE h.engagement_id = ? AND hp.state = 'open' "
            "GROUP BY hp.port "
            "ORDER BY host_count DESC, hp.port ASC "
            "LIMIT ?",
            (engagement_id, limit),
        )
        port_rows = cursor.fetchall()
        if not port_rows:
            return []

        ports = [r[0] for r in port_rows]
        placeholders = ','.join(['?'] * len(ports))
        cursor.execute(
            f"SELECT hp.port, hp.service, COUNT(*) AS n "
            f"FROM host_ports hp JOIN hosts h ON h.id = hp.host_id "
            f"WHERE h.engagement_id = ? AND hp.state = 'open' "
            f"AND hp.port IN ({placeholders}) "
            f"AND hp.service IS NOT NULL AND hp.service != '' "
            f"GROUP BY hp.port, hp.service "
            f"ORDER BY hp.port, n DESC, hp.service ASC",
            (engagement_id, *ports),
        )
        # Pick first (most common) service per port
        service_by_port: Dict[int, str] = {}
        for port, service, _ in cursor.fetchall():
            service_by_port.setdefault(port, service)

        return [
            {'port': p, 'host_count': c, 'service': service_by_port.get(p)}
            for p, c in port_rows
        ]

    def get_host_status(self, engagement_id: int) -> Dict[str, int]:
        """Mutually-exclusive host status counts using priority order:
        rooted > shell-only > reviewed > flagged > out_of_scope > untouched.
        Each host is counted exactly once.
        """
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT "
            "  SUM(CASE WHEN rooted = 1 THEN 1 ELSE 0 END) AS rooted, "
            "  SUM(CASE WHEN rooted = 0 AND shell = 1 THEN 1 ELSE 0 END) AS shell_only, "
            "  SUM(CASE WHEN rooted = 0 AND shell = 0 AND reviewed = 1 THEN 1 ELSE 0 END) AS reviewed, "
            "  SUM(CASE WHEN rooted = 0 AND shell = 0 AND reviewed = 0 AND flagged = 1 THEN 1 ELSE 0 END) AS flagged, "
            "  SUM(CASE WHEN rooted = 0 AND shell = 0 AND reviewed = 0 AND flagged = 0 AND out_of_scope = 1 THEN 1 ELSE 0 END) AS out_of_scope, "
            "  SUM(CASE WHEN rooted = 0 AND shell = 0 AND reviewed = 0 AND flagged = 0 AND out_of_scope = 0 THEN 1 ELSE 0 END) AS untouched, "
            "  COUNT(*) AS total "
            "FROM hosts WHERE engagement_id = ?",
            (engagement_id,),
        )
        row = cursor.fetchone()
        return {
            'rooted': row[0] or 0,
            'shell_only': row[1] or 0,
            'reviewed': row[2] or 0,
            'flagged': row[3] or 0,
            'out_of_scope': row[4] or 0,
            'untouched': row[5] or 0,
            'total': row[6] or 0,
        }

    def get_top_services(self, engagement_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Top N services by distinct host count (open ports only)."""
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT COALESCE(NULLIF(hp.service, ''), '(unknown)') AS service, "
            "COUNT(DISTINCT hp.host_id) AS host_count "
            "FROM host_ports hp JOIN hosts h ON h.id = hp.host_id "
            "WHERE h.engagement_id = ? AND hp.state = 'open' "
            "GROUP BY COALESCE(NULLIF(hp.service, ''), '(unknown)') "
            "ORDER BY host_count DESC, service ASC "
            "LIMIT ?",
            (engagement_id, limit),
        )
        return [{'service': r[0], 'host_count': r[1]} for r in cursor.fetchall()]

    def get_findings_over_time(self, engagement_id: int) -> List[Dict[str, Any]]:
        """Per-day cumulative finding counts.

        Returns a list of {'day': 'YYYY-MM-DD', 'cumulative': int} dicts —
        one row per day on which at least one finding was created, in
        ascending date order. The 'cumulative' value is the running total
        of findings through that day. Days with zero new findings are
        omitted (sparse series, not dense).
        """
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT day, SUM(n) OVER (ORDER BY day) AS cumulative FROM ("
            "  SELECT DATE(created_at) AS day, COUNT(*) AS n "
            "  FROM engagement_findings "
            "  WHERE engagement_id = ? "
            "  GROUP BY day"
            ") ORDER BY day ASC",
            (engagement_id,),
        )
        return [{'day': r[0], 'cumulative': r[1]} for r in cursor.fetchall()]

    def get_color_categories(self, engagement_id: int) -> List[Dict[str, Any]]:
        """Host counts grouped by color_category. NULL is preserved as None."""
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT color_category, COUNT(*) AS n FROM hosts "
            "WHERE engagement_id = ? "
            "GROUP BY color_category "
            "ORDER BY n DESC",
            (engagement_id,),
        )
        return [{'color': r[0], 'count': r[1]} for r in cursor.fetchall()]

    def get_test_execution_summary(self, engagement_id: int) -> Dict[str, Any]:
        """Per-status execution counts plus total."""
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT status, COUNT(*) AS n FROM test_executions "
            "WHERE engagement_id = ? GROUP BY status ORDER BY n DESC",
            (engagement_id,),
        )
        by_status = [{'status': r[0], 'count': r[1]} for r in cursor.fetchall()]
        return {
            'total': sum(r['count'] for r in by_status),
            'by_status': by_status,
        }

    def get_scan_vulnerabilities(self, engagement_id: int) -> Dict[str, int]:
        """Aggregate individual vulnerability counts from imported tool scans.

        Walks evidence.metadata JSON for the engagement and tallies per-vuln
        severity counts from supported tools:
            - Nessus: each host's vulnerabilities array, severity 4/3/2/1
              maps to critical/high/medium/low.
            - Burp Suite: metadata.summary.by_severity {Critical, High,
              Medium, Low} integer counts.

        Returns a dict {'critical', 'high', 'medium', 'low'}. Mirrors the
        legacy client-side computation in refreshEvidenceStats() so the
        dashboard agrees with the sidebar's Vulnerability Stats panel.

        Malformed metadata rows are skipped silently — this is best-effort
        aggregation, not validation.
        """
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT metadata FROM evidence "
            "WHERE engagement_id = ? AND metadata IS NOT NULL AND metadata != ''",
            (engagement_id,),
        )

        counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
        nessus_severity_map = {4: 'critical', 3: 'high', 2: 'medium', 1: 'low'}

        for (meta_str,) in cursor.fetchall():
            try:
                meta = json.loads(meta_str) if isinstance(meta_str, str) else meta_str
            except (TypeError, ValueError):
                continue
            if not isinstance(meta, dict):
                continue

            tool = (meta.get('tool') or '').lower()

            if tool == 'nessus' and isinstance(meta.get('hosts'), list):
                for host in meta['hosts']:
                    if not isinstance(host, dict):
                        continue
                    vulns = host.get('vulnerabilities')
                    if not isinstance(vulns, list):
                        continue
                    for vuln in vulns:
                        if not isinstance(vuln, dict):
                            continue
                        bucket = nessus_severity_map.get(vuln.get('severity'))
                        if bucket:
                            counts[bucket] += 1

            elif tool in ('burp_suite', 'burp'):
                summary = meta.get('summary') or {}
                by_sev = summary.get('by_severity') or {}
                for label_in, label_out in (
                    ('Critical', 'critical'),
                    ('High',     'high'),
                    ('Medium',   'medium'),
                    ('Low',      'low'),
                ):
                    try:
                        counts[label_out] += int(by_sev.get(label_in) or 0)
                    except (TypeError, ValueError):
                        continue

        return counts
