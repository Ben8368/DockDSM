#!/usr/bin/env python3
"""Read-only, offline component admission. This is not a legal authorization."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('source_audit', ROOT / 'scripts/audit-bootloader-source.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
MANIFEST = 'research/bootloader/component-manifest.json'
COMPONENTS = frozenset(('core', 'buildroot-essential', 'buildroot-evo', 'grub', 'grub-seed',
                        'genarc', 'sshx', 'kpatch', 'memtest', 'lkm', 'custom', 'modules',
                        'addons', 'configs', 'patches', 'theme'))
STATES = {'BLOCKED', 'REVIEW_REQUIRED', 'APPROVED'}
GATES = ('source_import', 'combined_build', 'distribution')
REQUIREMENTS = {
    'source_import': ('source_complete', 'license_scope', 'rights_review', 'scope_review'),
    'combined_build': ('toolchain_locked', 'dependencies_closed', 'rebuild_verified'),
    'distribution': ('binary_correspondence', 'distribution_review'),
}


def fail(message):
    raise ValueError(message)


def fields(value, names):
    if not isinstance(value, dict) or set(value) != set(names.split()):
        fail('schema fields mismatch: ' + names)


def text(value):
    if not isinstance(value, str) or not value.strip():
        fail('nonempty text required')


def digest(value, length=64):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{' + str(length) + '}', value):
        fail('invalid digest')


def strings(value, allow_empty=True):
    if not isinstance(value, list) or (not value and not allow_empty):
        fail('text list required')
    for item in value:
        text(item)
    if len(value) != len(set(value)):
        fail('duplicate list item')


def relative(value):
    text(value)
    if (any(c in value for c in ('\\', ':', '\x00')) or value.startswith('/')
            or any(p in ('', '.', '..') for p in value.split('/'))):
        fail('unsafe relative path')
    return PurePosixPath(value)


def local(root, value):
    """No absolute paths, traversal, NTFS streams, symlinks/junction escapes."""
    relative(value)
    candidate = root / value
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
        fail('local evidence outside workspace or not a file')
    return resolved


def pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            fail('duplicate JSON key')
        result[key] = value
    return result


def load(path):
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=pairs)


def validate(manifest, lock):
    """Validate the closed schema before opening any evidence or Git repository."""
    fields(manifest, 'schema_version source_lock observations baseline_mapping components')
    if type(manifest['schema_version']) is not int or manifest['schema_version'] != 1:
        fail('unsupported manifest schema')
    relative(manifest['source_lock'])
    relative(manifest['observations'])
    mapping = manifest['baseline_mapping']
    if not isinstance(mapping, dict) or set(mapping) != COMPONENTS:
        fail('original sixteen audit objects must be mapped individually')
    for value in mapping.values():
        text(value)
    if len(set(mapping.values())) != len(COMPONENTS):
        fail('baseline mapping is not one-to-one')
    if not isinstance(manifest['components'], list):
        fail('components must be a list')
    seen = set()
    for component in manifest['components']:
        fields(component, 'id name origin source license artifacts build evidence conditions admission blockers next_actions')
        cid = component['id']
        text(cid)
        if cid in seen:
            fail('duplicate component ID')
        seen.add(cid)
        text(component['name'])
        fields(component['origin'], 'repository paths identity')
        origin = component['origin']
        text(origin['repository'])
        if not origin['repository'].startswith('https://'):
            fail('repository must be an HTTPS origin')
        strings(origin['paths'], False)
        for path in origin['paths']:
            if path != '/':
                relative(path)
        # All commit/tree facts are referenced, never copied into this manifest.
        if origin['identity'] not in ('source-lock', 'observations', 'unresolved'):
            fail('unknown identity reference')
        fields(component['source'], 'availability evidence notes')
        if component['source']['availability'] not in ('partial', 'unavailable', 'complete'):
            fail('unknown source availability')
        text(component['source']['notes'])
        fields(component['license'], 'declarations copyright evidence unresolved')
        strings(component['license']['declarations'], False)
        strings(component['license']['copyright'], False)
        strings(component['license']['unresolved'])
        fields(component['build'], 'entrypoints toolchain dependencies reproducibility')
        for key in ('entrypoints', 'toolchain', 'dependencies'):
            strings(component['build'][key])
        text(component['build']['reproducibility'])
        if not isinstance(component['evidence'], dict) or not component['evidence']:
            fail('component evidence required')
        for eid, evidence in component['evidence'].items():
            text(eid)
            fields(evidence, 'kind path sha256 bytes locator')
            if evidence['kind'] not in ('locked', 'git', 'local'):
                fail('unknown evidence kind')
            relative(evidence['path'])
            text(evidence['locator'])
            if evidence['kind'] == 'locked':
                expected_url = lock['upstream']['repository'].removesuffix('.git') + '/blob/' + lock['upstream']['revision'] + '/' + evidence['path']
                if evidence['locator'] != expected_url:
                    fail('locked evidence locator disagrees with source-lock')
                if evidence['path'] not in lock['evidence']:
                    fail('unknown source-lock evidence')
                if evidence['sha256'] is not None or evidence['bytes'] is not None:
                    fail('locked facts must not be duplicated')
            else:
                digest(evidence['sha256'])
                if type(evidence['bytes']) is not int or evidence['bytes'] < 0:
                    fail('invalid evidence size')
        for section in ('source', 'license'):
            strings(component[section]['evidence'])
            if any(e not in component['evidence'] for e in component[section]['evidence']):
                fail('unknown source/license evidence reference')
        if not isinstance(component['artifacts'], list):
            fail('artifact list required')
        artifact_paths = set()
        for artifact in component['artifacts']:
            fields(artifact, 'path kind evidence source_relation')
            text(artifact['path'])
            if artifact['path'] in artifact_paths:
                fail('duplicate artifact path')
            artifact_paths.add(artifact['path'])
            if artifact['kind'] not in ('pinned_blob', 'unlocked_release', 'placeholder'):
                fail('unknown artifact kind')
            if artifact['evidence'] is not None and artifact['evidence'] not in component['evidence']:
                fail('unknown artifact evidence')
            if artifact['kind'] in ('pinned_blob', 'placeholder') and artifact['evidence'] is None:
                fail('pinned artifact requires evidence')
            if artifact['kind'] in ('pinned_blob', 'placeholder'):
                relative(artifact['path'])
                proof = component['evidence'][artifact['evidence']]
                if proof['kind'] not in ('locked', 'git') or proof['path'] != artifact['path']:
                    fail('artifact must reference its exact pinned Git blob')
                size = lock['evidence'][proof['path']]['bytes'] if proof['kind'] == 'locked' else proof['bytes']
                if artifact['kind'] == 'pinned_blob' and size == 0:
                    fail('empty artifact is a placeholder, not a pinned binary')
            text(artifact['source_relation'])
        requirements = {r for group in REQUIREMENTS.values() for r in group}
        if not isinstance(component['conditions'], dict) or set(component['conditions']) != requirements:
            fail('admission conditions incomplete')
        for requirement, condition in component['conditions'].items():
            fields(condition, 'result evidence explanation')
            if condition['result'] not in ('missing', 'verified', 'conflict', 'excluded'):
                fail('unknown condition result')
            strings(condition['evidence'])
            if any(e not in component['evidence'] for e in condition['evidence']):
                fail('unknown condition evidence')
            text(condition['explanation'])
            if condition['result'] == 'verified' and not condition['evidence']:
                fail('verified condition requires evidence')
        fields(component['admission'], 'status source_import combined_build distribution')
        if component['admission']['status'] not in STATES:
            fail('unknown admission status')
        if any(type(component['admission'][gate]) is not bool for gate in GATES):
            fail('gate claims must be booleans')
        strings(component['blockers'])
        strings(component['next_actions'], False)
    if seen != COMPONENTS:
        fail('unregistered or missing component')


def tree_identity(rows):
    """Reconstruct recursive Git trees from metadata; never claim that blobs exist."""
    children = {}
    expected = {}
    for path, mode, oid, size in rows:
        relative(path)
        digest(oid, 40)
        if mode not in ('040000', '100644', '100755', '120000', '160000'):
            fail('unsupported remote tree mode')
        if path in expected:
            fail('duplicate remote tree path')
        expected[path] = (mode, oid)
        parent, _, name = path.rpartition('/')
        children.setdefault(parent, []).append((name, mode, oid))
    def build(directory):
        raw = b''
        for name, mode, oid in sorted(children.get(directory, []), key=lambda row: (row[0] + ('/' if row[1] == '040000' else '')).encode('utf-8')):
            path = directory + '/' + name if directory else name
            if mode == '040000' and build(path) != oid:
                fail('remote subtree identity mismatch')
            raw += mode.lstrip('0').encode() + b' ' + name.encode('utf-8') + b'\0' + bytes.fromhex(oid)
        return hashlib.sha1(b'tree ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    for directory in children:
        if directory and (directory not in expected or expected[directory][0] != '040000'):
            fail('remote tree missing parent')
    return build('')


def verify_observations(observations, root=ROOT):
    """Verify remote tree identities and captured texts, not a complete source delivery."""
    if not isinstance(observations, dict) or not isinstance(observations.get('repositories'), dict):
        fail('invalid observation receipt')
    if not observations['repositories']:
        return
    inventory = observations['tree_inventory']
    fields(inventory, 'path bytes sha256')
    digest(inventory['sha256'])
    raw_inventory = local(root, inventory['path']).read_bytes()
    if (len(raw_inventory) != inventory['bytes']
            or hashlib.sha256(raw_inventory).hexdigest() != inventory['sha256']):
        fail('remote tree inventory digest mismatch')
    trees = json.loads(raw_inventory, object_pairs_hook=pairs)
    if set(trees) != set(observations['repositories']):
        fail('remote tree inventory coverage mismatch')
    for name, repo in observations['repositories'].items():
        digest(repo['inspection_commit'], 40)
        digest(repo['tree'], 40)
        if repo['truncated'] is not False or tree_identity(trees[name]) != repo['tree']:
            fail('remote inspection tree identity/truncation mismatch')
        if len(trees[name]) != repo['tree_summary']['entry_count']:
            fail('remote tree count mismatch')
        by_path = {row[0]: row for row in trees[name]}
        for path, item in repo['texts'].items():
            raw = item['text'].encode('utf-8')
            oid = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
            if (oid != item['oid'] or by_path[path][2] != oid
                    or hashlib.sha256(raw).hexdigest() != item['sha256'] or len(raw) != item['bytes']):
                fail('observation text identity mismatch')


def verify_repository_boundary(root, source):
    if not source.resolve(strict=True).is_relative_to(root.resolve()):
        fail('source outside workspace')
    # gitdir/commondir and alternates can otherwise bypass filesystem path checks.
    marker = source / '.git'
    if not marker.resolve(strict=True).is_relative_to(root.resolve()):
        fail('Git marker outside workspace')
    if marker.is_file():
        value = marker.read_text(encoding='utf-8').strip()
        if not value.startswith('gitdir: '):
            fail('invalid gitdir')
        gitdir = (source / value[8:]).resolve(strict=True)
    else:
        gitdir = marker.resolve(strict=True)
    for directory in (gitdir,):
        if not directory.is_relative_to(root.resolve()):
            fail('Git storage outside authorized workspace')
    common = gitdir / 'commondir'
    if common.exists():
        if not common.resolve().is_relative_to(root.resolve()):
            fail('Git common marker outside workspace')
        shared = (gitdir / common.read_text(encoding='utf-8').strip()).resolve(strict=True)
        if not shared.is_relative_to(root.resolve()):
            fail('Git common storage outside authorized workspace')
    else:
        shared = gitdir
    # External object stores are never part of an admission inspection.
    for directory in set((gitdir, shared)):
        for entry in directory.rglob('*'):
            if (entry.is_symlink() or entry.is_junction()) and not entry.resolve().is_relative_to(root.resolve()):
                fail('Git storage link outside workspace')
        for name in ('config', 'config.worktree'):
            config = directory / name
            if config.exists() and re.search(r'\[\s*include', config.read_text(encoding='utf-8').replace('\\\n', ''), re.I):
                fail('Git config includes are not allowed for offline inspection')
        for name in ('alternates', 'http-alternates'):
            alternate = directory / 'objects/info' / name
            if alternate.exists() and alternate.read_bytes().strip():
                fail('Git alternates are not allowed')
        for path in (directory / 'config', directory / 'objects', directory / 'objects/info'):
            if path.exists() and not path.resolve().is_relative_to(root.resolve()):
                fail('Git storage link outside workspace')


def verify_receipt_graph(edges):
    """Reviewed conditions cannot use one another as circular evidence."""
    visited, active = set(), set()
    def visit(eid):
        if eid in active:
            fail('circular verification receipt inputs')
        if eid in visited:
            return
        active.add(eid)
        for dependency in edges.get(eid, ()):
            visit(dependency)
        active.remove(eid)
        visited.add(eid)
    for eid in edges:
        visit(eid)


def evaluate(root, manifest_path=MANIFEST, source_path='vendor/arc'):
    root = root.resolve(strict=True)
    manifest = load(local(root, manifest_path))
    if not isinstance(manifest, dict) or not isinstance(manifest.get('source_lock'), str):
        fail('manifest/source lock reference required')
    lock = load(local(root, manifest['source_lock']))
    validate(manifest, lock)
    observations = load(local(root, manifest['observations']))
    verify_observations(observations, root)
    relative(source_path)
    source = (root / source_path).resolve(strict=True)
    verify_repository_boundary(root, source)
    audit.inventory(source, lock)
    source_paths = [row.split(b'\t', 1)[1].decode('utf-8') for row in
                    audit.git(source, 'ls-tree', '-r', '-z', lock['upstream']['revision']).split(b'\0') if row]
    output = []
    for component in manifest['components']:
        origin = component['origin']
        if origin['identity'] == 'source-lock':
            if origin['repository'].removesuffix('.git') != lock['upstream']['repository'].removesuffix('.git'):
                fail('origin disagrees with source-lock')
            identity = lock['upstream']
        elif origin['identity'] == 'observations':
            key = origin['repository'].rsplit('/', 1)[-1]
            observed = observations['repositories'][key]
            if origin['repository'] != observed['repository']:
                fail('origin disagrees with inspection snapshot')
            identity = dict(repository=observed['repository'], revision=observed['inspection_commit'], tree=observed['tree'])
        else:
            key = origin['repository'].rsplit('/', 1)[-1]
            if key not in observations['unavailable']:
                fail('unresolved origin has no observation')
            unavailable = observations['unavailable'][key]
            if not any(item['url'] == origin['repository'] for item in unavailable['public']):
                fail('unresolved origin disagrees with observed repository URL')
            identity = None
        if origin['identity'] != 'unresolved':
            paths = source_paths if origin['identity'] == 'source-lock' else [row[0] for row in
                    load(local(root, observations['tree_inventory']['path']))[key]]
            for path in origin['paths']:
                if path != '/' and not any(p == path or p.startswith(path + '/') for p in paths):
                    fail('original path absent from pinned identity: ' + component['id'])
        verified = set()
        for eid, evidence in component['evidence'].items():
            kind = evidence['kind']
            if kind == 'locked':
                verified.add(eid)  # inventory already checked these exact Git blobs
                continue
            if kind == 'local':
                raw = local(root, evidence['path']).read_bytes()
                if evidence['path'] == manifest['observations']:
                    prefix = 'unavailable/' if origin['identity'] == 'unresolved' else 'repositories/'
                    if evidence['locator'] != prefix + origin['repository'].rsplit('/', 1)[-1]:
                        fail('observation locator disagrees with component origin')
            else:
                # Paths never become Git revision expressions; resolve via ls-tree first.
                entries = audit.git(source, 'ls-tree', '-z', lock['upstream']['revision'],
                                    '--', evidence['path']).split(b'\0')
                exact = [row for row in entries if row and row.split(b'\t', 1)[1].decode() == evidence['path']]
                if len(exact) != 1 or exact[0].split()[1] != b'blob':
                    fail('evidence is not a pinned Git blob')
                oid = exact[0].split()[2].decode()
                raw = audit.git(source, 'cat-file', 'blob', oid)
            if len(raw) != evidence['bytes'] or hashlib.sha256(raw).hexdigest() != evidence['sha256']:
                fail('evidence digest/size mismatch: ' + component['id'])
            if kind == 'git':
                expected_url = lock['upstream']['repository'].removesuffix('.git') + '/blob/' + lock['upstream']['revision'] + '/' + evidence['path']
                if evidence['locator'] != expected_url:
                    fail('Git evidence locator disagrees with fixed source')
            verified.add(eid)
        conditions = component['conditions']
        def satisfied(name):
            condition = conditions[name]
            return (condition['result'] == 'verified' and bool(condition['evidence'])
                    and all(e in verified for e in condition['evidence']))
        # A status/result edit cannot promote a URL/hash into a review or rebuild receipt.
        receipt_edges = {}
        for name, condition in conditions.items():
            if condition['result'] != 'verified':
                continue
            receipts = []
            for eid in condition['evidence']:
                evidence = component['evidence'][eid]
                if evidence['kind'] != 'local' or evidence['path'] == manifest['observations']:
                    continue
                receipt = load(local(root, evidence['path']))
                fields(receipt, 'schema_version component condition decision source_identity inputs reviewer explanation')
                if (type(receipt['schema_version']) is not int or receipt['schema_version'] != 1
                        or receipt['component'] != component['id'] or receipt['condition'] != name
                        or receipt['decision'] != 'verified' or identity is None
                        or receipt['source_identity'] != identity):
                    fail('condition receipt subject/identity mismatch')
                strings(receipt['inputs'], False)
                if any(e == eid or e not in verified for e in receipt['inputs']):
                    fail('condition receipt inputs missing or circular')
                text(receipt['reviewer'])
                text(receipt['explanation'])
                receipt_edges[eid] = receipt['inputs']
                receipts.append(receipt)
            if not receipts:
                fail('verified condition lacks a subject-bound review/verification receipt')
        verify_receipt_graph(receipt_edges)
        source_ok = (component['source']['availability'] == 'complete'
                     and bool(component['source']['evidence'])
                     and bool(component['license']['evidence'])
                     and not component['license']['unresolved']
                     and component['origin']['identity'] == 'source-lock'
                     and all(satisfied(r) for r in REQUIREMENTS['source_import']))
        pinned_artifacts = all(a['kind'] == 'pinned_blob' and a['evidence'] in verified
                               for a in component['artifacts'])
        build_ok = (source_ok and pinned_artifacts and not lock['unlocked_dependencies']
                    and all(satisfied(r) for r in REQUIREMENTS['combined_build']))
        distribution_ok = (build_ok and all(satisfied(r) for r in REQUIREMENTS['distribution'])
                           and lock['distribution']['combined_artifact_allowed'] is True)
        computed = dict(source_import=source_ok, combined_build=build_ok, distribution=distribution_ok)
        for gate, allowed in computed.items():
            if component['admission'][gate] != allowed:
                fail('gate claim disagrees with evidence: ' + component['id'] + '/' + gate)
        ready = all(computed.values()) and not component['blockers']
        if (component['admission']['status'] == 'APPROVED') != ready:
            fail('APPROVED claim disagrees with evidence: ' + component['id'])
        if component['admission']['status'] == 'REVIEW_REQUIRED' and (
                component['source']['availability'] == 'unavailable'
                or not component['source']['evidence'] or not component['license']['evidence']
                or component['origin']['identity'] == 'unresolved'):
            fail('REVIEW_REQUIRED needs inspectable source and license evidence')
        if not ready and not component['blockers']:
            fail('unresolved component requires blockers')
        output.append(dict(id=component['id'], status=component['admission']['status'], **computed,
                           missing=[r for r in conditions if not satisfied(r)], blockers=component['blockers']))
    counts = {state: sum(c['status'] == state for c in output) for state in sorted(STATES)}
    return dict(schema_version=1, offline=True, read_only=True, counts=counts, components=output,
                strict_pass=all(c['status'] == 'APPROVED' for c in output),
                limitation='Evidence integrity and recorded technical gates; not a rights-holder permission or legal opinion.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--strict', action='store_true')
    parser.add_argument('--manifest', default=MANIFEST, help='workspace-relative manifest')
    parser.add_argument('--source', default='vendor/arc', help='workspace-relative pinned source')
    args = parser.parse_args()
    try:
        result = evaluate(ROOT, args.manifest, args.source)
    except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError, RecursionError, subprocess.CalledProcessError) as error:
        # Never leak remote URLs, credentials or Git diagnostics from exceptions.
        message = 'Git source inspection failed' if isinstance(error, subprocess.CalledProcessError) else 'invalid or unavailable evidence'
        print('Bootloader admission failed: ' + message, file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if args.strict and not result['strict_pass'] else 0


if __name__ == '__main__':
    sys.exit(main())
