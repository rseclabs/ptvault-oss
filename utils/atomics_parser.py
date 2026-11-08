"""
Atomic Red Team YAML Parser for PTVault.
Parses Atomic Red Team test YAML files and populates the database.
"""

import os
import json
import yaml
from datetime import datetime
from glob import glob


# MITRE ATT&CK Tactic mapping (technique prefix to tactic)
TECHNIQUE_TACTIC_MAP = {
    'T1001': 'command-and-control',
    'T1002': 'exfiltration',
    'T1003': 'credential-access',
    'T1004': 'persistence',
    'T1005': 'collection',
    'T1006': 'defense-evasion',
    'T1007': 'discovery',
    'T1008': 'command-and-control',
    'T1009': 'defense-evasion',
    'T1010': 'discovery',
    'T1011': 'exfiltration',
    'T1012': 'discovery',
    'T1013': 'persistence',
    'T1014': 'defense-evasion',
    'T1015': 'persistence',
    'T1016': 'discovery',
    'T1017': 'lateral-movement',
    'T1018': 'discovery',
    'T1019': 'persistence',
    'T1020': 'exfiltration',
    'T1021': 'lateral-movement',
    'T1022': 'exfiltration',
    'T1023': 'persistence',
    'T1024': 'command-and-control',
    'T1025': 'collection',
    'T1026': 'command-and-control',
    'T1027': 'defense-evasion',
    'T1028': 'execution',
    'T1029': 'exfiltration',
    'T1030': 'exfiltration',
    'T1031': 'persistence',
    'T1032': 'command-and-control',
    'T1033': 'discovery',
    'T1034': 'persistence',
    'T1035': 'execution',
    'T1036': 'defense-evasion',
    'T1037': 'persistence',
    'T1038': 'persistence',
    'T1039': 'collection',
    'T1040': 'credential-access',
    'T1041': 'exfiltration',
    'T1042': 'persistence',
    'T1043': 'command-and-control',
    'T1044': 'persistence',
    'T1045': 'defense-evasion',
    'T1046': 'discovery',
    'T1047': 'execution',
    'T1048': 'exfiltration',
    'T1049': 'discovery',
    'T1050': 'persistence',
    'T1051': 'lateral-movement',
    'T1052': 'exfiltration',
    'T1053': 'execution',
    'T1054': 'defense-evasion',
    'T1055': 'defense-evasion',
    'T1056': 'credential-access',
    'T1057': 'discovery',
    'T1058': 'persistence',
    'T1059': 'execution',
    'T1060': 'persistence',
    'T1061': 'execution',
    'T1062': 'persistence',
    'T1063': 'discovery',
    'T1064': 'execution',
    'T1065': 'command-and-control',
    'T1066': 'defense-evasion',
    'T1067': 'persistence',
    'T1068': 'privilege-escalation',
    'T1069': 'discovery',
    'T1070': 'defense-evasion',
    'T1071': 'command-and-control',
    'T1072': 'execution',
    'T1073': 'defense-evasion',
    'T1074': 'collection',
    'T1075': 'lateral-movement',
    'T1076': 'lateral-movement',
    'T1077': 'lateral-movement',
    'T1078': 'initial-access',
    'T1079': 'command-and-control',
    'T1080': 'lateral-movement',
    'T1081': 'credential-access',
    'T1082': 'discovery',
    'T1083': 'discovery',
    'T1084': 'persistence',
    'T1085': 'execution',
    'T1086': 'execution',
    'T1087': 'discovery',
    'T1088': 'privilege-escalation',
    'T1089': 'defense-evasion',
    'T1090': 'command-and-control',
    'T1091': 'initial-access',
    'T1092': 'command-and-control',
    'T1093': 'defense-evasion',
    'T1094': 'command-and-control',
    'T1095': 'command-and-control',
    'T1096': 'defense-evasion',
    'T1097': 'lateral-movement',
    'T1098': 'persistence',
    'T1099': 'defense-evasion',
    'T1100': 'persistence',
    'T1101': 'persistence',
    'T1102': 'command-and-control',
    'T1103': 'persistence',
    'T1104': 'command-and-control',
    'T1105': 'command-and-control',
    'T1106': 'execution',
    'T1107': 'defense-evasion',
    'T1108': 'defense-evasion',
    'T1109': 'defense-evasion',
    'T1110': 'credential-access',
    'T1111': 'credential-access',
    'T1112': 'defense-evasion',
    'T1113': 'collection',
    'T1114': 'collection',
    'T1115': 'collection',
    'T1116': 'defense-evasion',
    'T1117': 'execution',
    'T1118': 'execution',
    'T1119': 'collection',
    'T1120': 'discovery',
    'T1121': 'execution',
    'T1122': 'defense-evasion',
    'T1123': 'collection',
    'T1124': 'discovery',
    'T1125': 'collection',
    'T1126': 'defense-evasion',
    'T1127': 'execution',
    'T1128': 'persistence',
    'T1129': 'execution',
    'T1130': 'defense-evasion',
    'T1131': 'persistence',
    'T1132': 'command-and-control',
    'T1133': 'initial-access',
    'T1134': 'privilege-escalation',
    'T1135': 'discovery',
    'T1136': 'persistence',
    'T1137': 'persistence',
    'T1138': 'persistence',
    'T1139': 'credential-access',
    'T1140': 'defense-evasion',
    'T1141': 'credential-access',
    'T1142': 'credential-access',
    'T1143': 'defense-evasion',
    'T1144': 'defense-evasion',
    'T1145': 'credential-access',
    'T1146': 'defense-evasion',
    'T1147': 'defense-evasion',
    'T1148': 'defense-evasion',
    'T1149': 'defense-evasion',
    'T1150': 'persistence',
    'T1151': 'defense-evasion',
    'T1152': 'execution',
    'T1153': 'execution',
    'T1154': 'execution',
    'T1155': 'execution',
    'T1156': 'persistence',
    'T1157': 'persistence',
    'T1158': 'defense-evasion',
    'T1159': 'persistence',
    'T1160': 'persistence',
    'T1161': 'persistence',
    'T1162': 'persistence',
    'T1163': 'persistence',
    'T1164': 'persistence',
    'T1165': 'persistence',
    'T1166': 'privilege-escalation',
    'T1167': 'credential-access',
    'T1168': 'persistence',
    'T1169': 'privilege-escalation',
    'T1170': 'execution',
    'T1171': 'credential-access',
    'T1172': 'command-and-control',
    'T1173': 'execution',
    'T1174': 'credential-access',
    'T1175': 'lateral-movement',
    'T1176': 'persistence',
    'T1177': 'execution',
    'T1178': 'privilege-escalation',
    'T1179': 'credential-access',
    'T1180': 'persistence',
    'T1181': 'defense-evasion',
    'T1182': 'persistence',
    'T1183': 'persistence',
    'T1184': 'lateral-movement',
    'T1185': 'collection',
    'T1186': 'defense-evasion',
    'T1187': 'credential-access',
    'T1188': 'command-and-control',
    'T1189': 'initial-access',
    'T1190': 'initial-access',
    'T1191': 'execution',
    'T1192': 'initial-access',
    'T1193': 'initial-access',
    'T1194': 'initial-access',
    'T1195': 'initial-access',
    'T1196': 'defense-evasion',
    'T1197': 'defense-evasion',
    'T1198': 'defense-evasion',
    'T1199': 'initial-access',
    'T1200': 'initial-access',
    'T1201': 'discovery',
    'T1202': 'defense-evasion',
    'T1203': 'execution',
    'T1204': 'execution',
    'T1205': 'command-and-control',
    'T1206': 'privilege-escalation',
    'T1207': 'defense-evasion',
    'T1208': 'credential-access',
    'T1209': 'persistence',
    'T1210': 'lateral-movement',
    'T1211': 'defense-evasion',
    'T1212': 'credential-access',
    'T1213': 'collection',
    'T1214': 'credential-access',
    'T1215': 'persistence',
    'T1216': 'defense-evasion',
    'T1217': 'discovery',
    'T1218': 'defense-evasion',
    'T1219': 'command-and-control',
    'T1220': 'defense-evasion',
    'T1221': 'defense-evasion',
    'T1222': 'defense-evasion',
    'T1223': 'execution',
    'T1480': 'defense-evasion',
    'T1482': 'discovery',
    'T1483': 'command-and-control',
    'T1484': 'defense-evasion',
    'T1485': 'impact',
    'T1486': 'impact',
    'T1487': 'impact',
    'T1488': 'impact',
    'T1489': 'impact',
    'T1490': 'impact',
    'T1491': 'impact',
    'T1492': 'impact',
    'T1493': 'impact',
    'T1494': 'impact',
    'T1495': 'impact',
    'T1496': 'impact',
    'T1497': 'defense-evasion',
    'T1498': 'impact',
    'T1499': 'impact',
    'T1500': 'defense-evasion',
    'T1501': 'persistence',
    'T1502': 'defense-evasion',
    'T1503': 'credential-access',
    'T1504': 'persistence',
    'T1505': 'persistence',
    'T1506': 'defense-evasion',
    'T1507': 'discovery',
    'T1508': 'defense-evasion',
    'T1509': 'command-and-control',
    'T1510': 'collection',
    'T1511': 'collection',
    'T1512': 'collection',
    'T1513': 'collection',
    'T1514': 'privilege-escalation',
    'T1515': 'defense-evasion',
    'T1516': 'defense-evasion',
    'T1517': 'collection',
    'T1518': 'discovery',
    'T1519': 'persistence',
    'T1520': 'defense-evasion',
    'T1521': 'command-and-control',
    'T1522': 'credential-access',
    'T1523': 'defense-evasion',
    'T1524': 'defense-evasion',
    'T1525': 'persistence',
    'T1526': 'discovery',
    'T1527': 'persistence',
    'T1528': 'credential-access',
    'T1529': 'impact',
    'T1530': 'collection',
    'T1531': 'impact',
    'T1532': 'collection',
    'T1533': 'collection',
    'T1534': 'lateral-movement',
    'T1535': 'defense-evasion',
    'T1536': 'defense-evasion',
    'T1537': 'exfiltration',
    'T1538': 'discovery',
    'T1539': 'credential-access',
    'T1540': 'defense-evasion',
    'T1541': 'defense-evasion',
    'T1542': 'persistence',
    'T1543': 'persistence',
    'T1544': 'command-and-control',
    'T1545': 'defense-evasion',
    'T1546': 'persistence',
    'T1547': 'persistence',
    'T1548': 'privilege-escalation',
    'T1549': 'defense-evasion',
    'T1550': 'lateral-movement',
    'T1551': 'defense-evasion',
    'T1552': 'credential-access',
    'T1553': 'defense-evasion',
    'T1554': 'persistence',
    'T1555': 'credential-access',
    'T1556': 'credential-access',
    'T1557': 'credential-access',
    'T1558': 'credential-access',
    'T1559': 'execution',
    'T1560': 'collection',
    'T1561': 'impact',
    'T1562': 'defense-evasion',
    'T1563': 'lateral-movement',
    'T1564': 'defense-evasion',
    'T1565': 'impact',
    'T1566': 'initial-access',
    'T1567': 'exfiltration',
    'T1568': 'command-and-control',
    'T1569': 'execution',
    'T1570': 'lateral-movement',
    'T1571': 'command-and-control',
    'T1572': 'command-and-control',
    'T1573': 'command-and-control',
    'T1574': 'persistence',
    'T1575': 'execution',
    'T1576': 'defense-evasion',
    'T1577': 'defense-evasion',
    'T1578': 'defense-evasion',
    'T1579': 'credential-access',
    'T1580': 'discovery',
    'T1581': 'collection',
    'T1582': 'collection',
    'T1583': 'resource-development',
    'T1584': 'resource-development',
    'T1585': 'resource-development',
    'T1586': 'resource-development',
    'T1587': 'resource-development',
    'T1588': 'resource-development',
    'T1589': 'reconnaissance',
    'T1590': 'reconnaissance',
    'T1591': 'reconnaissance',
    'T1592': 'reconnaissance',
    'T1593': 'reconnaissance',
    'T1594': 'reconnaissance',
    'T1595': 'reconnaissance',
    'T1596': 'reconnaissance',
    'T1597': 'reconnaissance',
    'T1598': 'reconnaissance',
    'T1599': 'defense-evasion',
    'T1600': 'defense-evasion',
    'T1601': 'defense-evasion',
    'T1602': 'collection',
    'T1603': 'discovery',
    'T1604': 'execution',
    'T1605': 'initial-access',
    'T1606': 'credential-access',
    'T1607': 'privilege-escalation',
    'T1608': 'resource-development',
    'T1609': 'execution',
    'T1610': 'execution',
    'T1611': 'privilege-escalation',
    'T1612': 'defense-evasion',
    'T1613': 'discovery',
    'T1614': 'discovery',
    'T1615': 'discovery',
    'T1616': 'defense-evasion',
    'T1617': 'persistence',
    'T1618': 'credential-access',
    'T1619': 'discovery',
    'T1620': 'defense-evasion',
    'T1621': 'credential-access',
    'T1622': 'defense-evasion',
    'T1623': 'execution',
    'T1624': 'persistence',
    'T1625': 'defense-evasion',
    'T1626': 'defense-evasion',
    'T1627': 'impact',
    'T1628': 'defense-evasion',
    'T1629': 'defense-evasion',
    'T1630': 'defense-evasion',
    'T1631': 'persistence',
    'T1632': 'defense-evasion',
    'T1633': 'discovery',
    'T1634': 'credential-access',
    'T1635': 'credential-access',
    'T1636': 'collection',
    'T1637': 'command-and-control',
    'T1638': 'defense-evasion',
    'T1639': 'exfiltration',
    'T1640': 'collection',
    'T1641': 'collection',
    'T1642': 'defense-evasion',
    'T1643': 'command-and-control',
    'T1644': 'impact',
    'T1645': 'impact',
    'T1646': 'exfiltration',
    'T1647': 'defense-evasion',
    'T1648': 'execution',
    'T1649': 'credential-access',
    'T1650': 'lateral-movement',
    'T1651': 'execution',
    'T1652': 'discovery',
    'T1653': 'privilege-escalation',
    'T1654': 'discovery',
    'T1655': 'defense-evasion',
    'T1656': 'defense-evasion',
    'T1657': 'impact',
    'T1658': 'discovery',
    'T1659': 'collection',
}


def get_tactic_for_technique(technique_id):
    """
    Get the tactic for a technique ID.
    Uses the base technique ID (without sub-technique).
    """
    base_technique = technique_id.split('.')[0]
    return TECHNIQUE_TACTIC_MAP.get(base_technique, 'unknown')


def parse_atomic_yaml(yaml_path):
    """
    Parse a single Atomic Red Team YAML file.

    Args:
        yaml_path: Path to the YAML file

    Returns:
        dict: Parsed atomic data or None if invalid
    """
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        if not data:
            return None

        # Validate required fields
        if 'attack_technique' not in data:
            return None

        return data

    except yaml.YAMLError as e:
        print(f"YAML error in {yaml_path}: {e}")
        return None
    except Exception as e:
        print(f"Error parsing {yaml_path}: {e}")
        return None


# ---------------------------------------------------------------------------
# In-place library import
# ---------------------------------------------------------------------------
# Test plans reference atomics by id, and foreign keys are not enforced, so
# the import must never re-key rows. Instead:
#   1. every existing row's atomic_test_index is parked at -1 - index,
#   2. each test from the YAML updates the row with the same
#      auto_generated_guid (or, for rows imported before GUIDs were stored,
#      the same technique + original position), or is inserted if new,
#   3. rows still parked are no longer upstream: deleted unless a test plan
#      uses them, in which case they are kept so the plan keeps working.

_ATOMIC_FIELDS = (
    'technique_id', 'technique_name', 'tactic', 'atomic_test_index',
    'atomic_test_name', 'description', 'supported_platforms', 'executor_name',
    'executor_command', 'executor_cleanup', 'input_arguments', 'dependencies',
    'elevation_required', 'atomic_guid',
)


# Fields that change what a test plan item runs. If a refresh changes any of
# them, plan items using the test are flagged for re-review (M-6): a reviewed
# plan must not start running different commands without anyone noticing.
_EXECUTION_FIELDS = ('executor_name', 'executor_command', 'executor_cleanup', 'input_arguments',
                     'dependencies', 'elevation_required')


class _ImportState(set):
    """The ids seen in this import, plus how many plan items were flagged for review."""
    plan_items_flagged = 0


def _begin_atomics_import(cursor):
    """Park existing rows' positions so incoming rows can't collide. Returns the 'seen' id set."""
    cursor.execute("UPDATE atomics SET atomic_test_index = -1 - atomic_test_index WHERE atomic_test_index >= 0")
    return _ImportState()


def _upsert_atomic(cursor, seen_ids, values):
    """Update the existing row for this test, or insert it. Keeps ids stable."""
    guid = values.get('atomic_guid') or None
    values['atomic_guid'] = guid
    row = None
    if guid:
        cursor.execute("SELECT id FROM atomics WHERE atomic_guid = ?", (guid,))
        row = cursor.fetchone()
    if row is None:
        # Rows imported before GUIDs were stored: same technique, same position
        cursor.execute(
            "SELECT id FROM atomics WHERE technique_id = ? AND atomic_test_index = ? AND atomic_guid IS NULL",
            (values['technique_id'], -1 - values['atomic_test_index'])
        )
        row = cursor.fetchone()
    if row is not None and row[0] in seen_ids:
        row = None   # already claimed by another test in this import

    if row is not None:
        cursor.execute(f"SELECT {', '.join(_EXECUTION_FIELDS)} FROM atomics WHERE id = ?", (row[0],))
        before = cursor.fetchone()
        if tuple(before) != tuple(values[field] for field in _EXECUTION_FIELDS):
            cursor.execute("UPDATE test_plan_items SET needs_review = 1 WHERE atomic_id = ? AND needs_review = 0",
                           (row[0],))
            if isinstance(seen_ids, _ImportState):
                seen_ids.plan_items_flagged += cursor.rowcount
        assignments = ', '.join(f"{field} = ?" for field in _ATOMIC_FIELDS)
        cursor.execute(
            f"UPDATE atomics SET {assignments} WHERE id = ?",
            [values[field] for field in _ATOMIC_FIELDS] + [row[0]]
        )
        atomic_id = row[0]
    else:
        placeholders = ', '.join('?' for _ in _ATOMIC_FIELDS)
        cursor.execute(
            f"INSERT INTO atomics ({', '.join(_ATOMIC_FIELDS)}) VALUES ({placeholders})",
            [values[field] for field in _ATOMIC_FIELDS]
        )
        atomic_id = cursor.lastrowid
    seen_ids.add(atomic_id)
    return atomic_id


def _finish_atomics_import(cursor, seen_ids):
    """
    Handle rows that are no longer in the library. Returns
    {'removed': n, 'kept_in_use': n}.
    """
    cursor.execute("SELECT id, technique_id, atomic_test_index FROM atomics WHERE atomic_test_index < 0")
    parked = [r for r in cursor.fetchall() if r[0] not in seen_ids]
    cursor.execute("SELECT DISTINCT atomic_id FROM test_plan_items WHERE atomic_id IS NOT NULL")
    in_use = {r[0] for r in cursor.fetchall()}

    removed = kept = 0
    for atomic_id, technique_id, parked_index in parked:
        if atomic_id not in in_use:
            cursor.execute("DELETE FROM atomics WHERE id = ?", (atomic_id,))
            removed += 1
            continue
        kept += 1
        # Restore its original position if no current test took it
        original = -1 - parked_index
        cursor.execute(
            "SELECT 1 FROM atomics WHERE technique_id = ? AND atomic_test_index = ?",
            (technique_id, original)
        )
        if cursor.fetchone() is not None:
            # Taken by a current test: use the next free slot in the technique.
            # (Never leave it negative: the next import parks rows at -1 - index.)
            cursor.execute(
                "SELECT COALESCE(MAX(atomic_test_index), -1) + 1 FROM atomics "
                "WHERE technique_id = ? AND atomic_test_index >= 0",
                (technique_id,)
            )
            original = cursor.fetchone()[0]
        cursor.execute("UPDATE atomics SET atomic_test_index = ? WHERE id = ?", (original, atomic_id))
    return {'removed': removed, 'kept_in_use': kept}


def parse_all_atomics(atomics_path, db_conn):
    """
    Parse all Atomic Red Team YAML files and populate the database.

    Args:
        atomics_path: Path to the atomics techniques folder
        db_conn: SQLite database connection

    Returns:
        dict: Statistics about parsing (total_techniques, total_tests)
    """
    cursor = db_conn.cursor()

    # Update in place (never re-key rows: test plans reference atomic ids)
    seen_ids = _begin_atomics_import(cursor)

    total_techniques = 0
    total_tests = 0
    errors = []

    # Find all technique folders (T1xxx or T1xxx.xxx)
    technique_folders = glob(os.path.join(atomics_path, 'T*'))

    for folder in technique_folders:
        if not os.path.isdir(folder):
            continue

        technique_id = os.path.basename(folder)

        # Find the YAML file in this folder
        yaml_files = glob(os.path.join(folder, f'{technique_id}.yaml'))
        if not yaml_files:
            continue

        yaml_path = yaml_files[0]
        data = parse_atomic_yaml(yaml_path)

        if not data:
            errors.append(f"Failed to parse {yaml_path}")
            continue

        technique_name = data.get('display_name', technique_id)
        tactic = get_tactic_for_technique(technique_id)
        atomic_tests = data.get('atomic_tests', [])

        if not atomic_tests:
            continue

        total_techniques += 1

        for test_index, test in enumerate(atomic_tests):
            try:
                # Extract test data
                test_name = test.get('name', f'Test {test_index + 1}')
                description = test.get('description', '')
                supported_platforms = test.get('supported_platforms', [])
                executor = test.get('executor', {})
                executor_name = executor.get('name', 'manual')
                executor_command = executor.get('command', '')
                executor_cleanup = executor.get('cleanup_command', '')
                input_arguments = test.get('input_arguments', {})
                dependencies = test.get('dependencies', [])
                elevation_required = 1 if (executor.get('elevation_required') or test.get('elevation_required')) else 0

                _upsert_atomic(cursor, seen_ids, {
                    'technique_id': technique_id,
                    'technique_name': technique_name,
                    'tactic': tactic,
                    'atomic_test_index': test_index,
                    'atomic_test_name': test_name,
                    'description': description,
                    'supported_platforms': json.dumps(supported_platforms) if supported_platforms else '[]',
                    'executor_name': executor_name,
                    'executor_command': executor_command,
                    'executor_cleanup': executor_cleanup,
                    'input_arguments': json.dumps(input_arguments) if input_arguments else '{}',
                    'dependencies': json.dumps(dependencies) if dependencies else '[]',
                    'elevation_required': elevation_required,
                    'atomic_guid': test.get('auto_generated_guid'),
                })

                total_tests += 1

            except Exception as e:
                errors.append(f"Error inserting test {test_name} from {technique_id}: {e}")

    retired = _finish_atomics_import(cursor, seen_ids)
    db_conn.commit()

    if errors:
        print(f"Parsing completed with {len(errors)} errors:")
        for error in errors[:10]:  # Show first 10 errors
            print(f"  - {error}")

    return {
        'total_techniques': total_techniques,
        'total_tests': total_tests,
        'errors': errors,
        'retired': retired,
        'plan_items_flagged': seen_ids.plan_items_flagged,
    }


def parse_all_atomics_with_progress(atomics_path, db_conn):
    """
    Parse all Atomic Red Team YAML files with progress updates.
    Yields progress dictionaries.

    Args:
        atomics_path: Path to the atomics techniques folder
        db_conn: SQLite database connection

    Yields:
        dict: Progress updates with percent, message, and final stats
    """
    cursor = db_conn.cursor()

    # Update in place (never re-key rows: test plans reference atomic ids)
    seen_ids = _begin_atomics_import(cursor)

    total_techniques = 0
    total_tests = 0
    errors = []

    # Find all technique folders (T1xxx or T1xxx.xxx)
    technique_folders = sorted(glob(os.path.join(atomics_path, 'T*')))
    total_folders = len(technique_folders)

    for idx, folder in enumerate(technique_folders):
        if not os.path.isdir(folder):
            continue

        technique_id = os.path.basename(folder)

        # Yield progress every 10 techniques
        if idx % 10 == 0:
            percent = int((idx / total_folders) * 100) if total_folders > 0 else 0
            yield {
                'percent': percent,
                'message': f'Parsing {technique_id}... ({idx}/{total_folders})'
            }

        # Find the YAML file in this folder
        yaml_files = glob(os.path.join(folder, f'{technique_id}.yaml'))
        if not yaml_files:
            continue

        yaml_path = yaml_files[0]
        data = parse_atomic_yaml(yaml_path)

        if not data:
            errors.append(f"Failed to parse {yaml_path}")
            continue

        technique_name = data.get('display_name', technique_id)
        tactic = get_tactic_for_technique(technique_id)
        atomic_tests = data.get('atomic_tests', [])

        if not atomic_tests:
            continue

        total_techniques += 1

        for test_index, test in enumerate(atomic_tests):
            try:
                test_name = test.get('name', f'Test {test_index + 1}')
                description = test.get('description', '')
                supported_platforms = test.get('supported_platforms', [])
                executor = test.get('executor', {})
                executor_name = executor.get('name', 'manual')
                executor_command = executor.get('command', '')
                executor_cleanup = executor.get('cleanup_command', '')
                input_arguments = test.get('input_arguments', {})
                dependencies = test.get('dependencies', [])
                elevation_required = 1 if (executor.get('elevation_required') or test.get('elevation_required')) else 0

                _upsert_atomic(cursor, seen_ids, {
                    'technique_id': technique_id,
                    'technique_name': technique_name,
                    'tactic': tactic,
                    'atomic_test_index': test_index,
                    'atomic_test_name': test_name,
                    'description': description,
                    'supported_platforms': json.dumps(supported_platforms) if supported_platforms else '[]',
                    'executor_name': executor_name,
                    'executor_command': executor_command,
                    'executor_cleanup': executor_cleanup,
                    'input_arguments': json.dumps(input_arguments) if input_arguments else '{}',
                    'dependencies': json.dumps(dependencies) if dependencies else '[]',
                    'elevation_required': elevation_required,
                    'atomic_guid': test.get('auto_generated_guid'),
                })

                total_tests += 1

            except Exception as e:
                errors.append(f"Error inserting test {test_name} from {technique_id}: {e}")

    retired = _finish_atomics_import(cursor, seen_ids)
    db_conn.commit()

    # Yield final stats
    yield {
        'percent': 100,
        'message': f'Parsed {total_techniques} techniques, {total_tests} tests',
        'stats': {
            'total_techniques': total_techniques,
            'total_tests': total_tests,
            'errors': errors,
            'retired': retired,
            'plan_items_flagged': seen_ids.plan_items_flagged,
        }
    }


def update_atomics_metadata(db_conn, atomics_path, stats, version='unknown'):
    """
    Update the atomics_metadata table with current status.

    Args:
        db_conn: SQLite database connection
        atomics_path: Path to the atomics folder
        stats: Parsing statistics dict
    """
    cursor = db_conn.cursor()

    # Use INSERT OR REPLACE for singleton row
    cursor.execute("""
        INSERT OR REPLACE INTO atomics_metadata (
            id, version, last_updated, total_techniques, total_tests, download_path
        ) VALUES (1, ?, ?, ?, ?, ?)
    """, (
        version,  # the pinned Atomic Red Team commit
        datetime.now().isoformat(),
        stats['total_techniques'],
        stats['total_tests'],
        atomics_path
    ))

    db_conn.commit()
