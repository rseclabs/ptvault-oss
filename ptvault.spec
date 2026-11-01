# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_all

block_cipher = None

# Collect all jose submodules dynamically
jose_hiddenimports = collect_submodules('jose')

# Collect flask_limiter and its full dependency chain (datas + binaries + hiddenimports)
fl_datas, fl_binaries, fl_hiddenimports = collect_all('flask_limiter')
lim_datas, lim_binaries, lim_hiddenimports = collect_all('limits')
os_datas, os_binaries, os_hiddenimports = collect_all('ordered_set')

extra_datas = fl_datas + lim_datas + os_datas
extra_binaries = fl_binaries + lim_binaries + os_binaries
extra_hiddenimports = fl_hiddenimports + lim_hiddenimports + os_hiddenimports

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[] + extra_binaries,
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        ('models/schema.sql', 'models'),
        ('models/migrations', 'models/migrations'),
        ('models/seed_templates.py', 'models'),
        ('.env.example', '.'),
    ] + extra_datas,
    hiddenimports=[
        'flask',
        'nacl',
        'nacl.signing',
        'nacl.encoding',
        'nacl.exceptions',
        'argon2',
        'argon2.exceptions',
        'argon2.low_level',
        'lxml',
        'lxml.etree',
        'libnmap',
        'libnmap.parser',
        'defusedxml',
        'defusedxml.ElementTree',
        'dotenv',
        'sqlite3',
        'sqlcipher3',
        'pysqlcipher3',
        'pysqlcipher3.dbapi2',
        # Feature registry (dynamically imports routes)
        'features',
        # Route blueprints (loaded dynamically via importlib in features.py)
        'routes',
        'routes.auth',
        'routes.dashboard',
        'routes.engagements',
        'routes.evidence',
        'routes.tags',
        'routes.hosts',
        'routes.commands',
        'routes.admin',
        'routes.shell_oneliners',
        'routes.filters',
        'routes.users',
        'routes.teams',
        'routes.clients',
        'routes.test',
        'routes.reporting',
        'routes.testplans',
        'routes.engagement_members',
        'routes.relationships',
        'routes.attack_maps',
        'routes.templates',
        # Middleware
        'middleware',
        'middleware.auth',
        # Model modules
        'models',
        'models.auth',
        'models.database',
        'models.encryption',
        'models.seed_templates',
        'models.migrations',
        'models.migrations.manager',
        # DAO modules (some are imported conditionally inside functions)
        'models.dao',
        'models.dao.base',
        'models.dao.client_dao',
        'models.dao.dashboard_dao',
        'models.dao.engagement_dao',
        'models.dao.evidence_dao',
        'models.dao.host_dao',
        'models.dao.note_tree_dao',
        'models.dao.report_dao',
        'models.dao.test_plan_dao',
        'models.dao.user_dao',
        'models.dao.template_dao',
        'models.dao.relationship_dao',
        'models.dao.attack_map_dao',
        'models.dao.team_dao',
        # Utility modules
        'utils',
        'utils.helpers',
        'utils.report_auto_populator',
        'utils.attack_map_svg',
        'utils.pdf_generator',
        'utils.markdown_export',
        'utils.template_renderer',
        'utils.audit_logger',
        'utils.error_handler',
        'utils.script_generator',
        'utils.host_extractor',
        'utils.file_helpers',
        'utils.atomics_downloader',
        'utils.atomics_parser',
        'utils.navigator_parser',
        'utils.migration_tags',
        # Parser modules
        'utils.parsers',
        'utils.parsers.registry',
        'utils.parsers.base_parser',
        'utils.parsers.nmap_parser',
        'utils.parsers.burp_parser',
        'utils.parsers.nessus_parser',
        'utils.parsers.zap_parser',
        'utils.parsers.qualys_parser',
        'utils.parsers.nuclei_parser',
        'utils.parsers.metasploit_parser',
        'utils.parsers.acunetix_parser',
        'utils.parsers.insightvm_parser',
        'utils.parsers.bloodhound_parser',
        'utils.parsers.crackmapexec_parser',
        # WeasyPrint for PDF generation
        'weasyprint',
        # python-docx for Word export
        'docx',
        'docx.shared',
        'docx.enum.text',
        # PyYAML - used by utils/atomics_parser.py
        'yaml',
        # requests - used by routes/admin.py (CyberChef) and utils/atomics_downloader.py
        'requests',
        'urllib3',
        'certifi',
        'charset_normalizer',
        'idna',
    ] + jose_hiddenimports + extra_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # cffi.vengine_cpy and cffi._imp_emulation use the deprecated 'imp'
        # module (removed in Python 3.12). These are only needed for cffi's
        # compile-time verifier, not at runtime with pre-built bindings.
        'cffi.vengine_cpy',
        'cffi.vengine_gen',
        'cffi._imp_emulation',
        'cffi.verifier',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ptvault',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
