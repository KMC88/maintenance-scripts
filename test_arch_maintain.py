#!/usr/bin/env python3
"""
Unit tests for arch_maintain.py

Uses only the standard library (unittest + unittest.mock) so no extra
dependency is introduced. Every external side effect (subprocess.run,
shutil.which) is mocked, so the tests never touch pacman, sudo, or the real
home directory.

Run with:
    python3 -m unittest -v
"""

import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest import mock

import arch_maintain
from arch_maintain import ArchMaintenance, Colors, parse_args


def completed(returncode=0):
    """Build a fake subprocess.CompletedProcess-like result."""
    return SimpleNamespace(returncode=returncode, stdout='', stderr='')


class SilentTestCase(unittest.TestCase):
    """Base case that swallows the script's stdout to keep test output clean."""

    def setUp(self):
        super().setUp()
        ctx = redirect_stdout(io.StringIO())
        ctx.__enter__()
        self.addCleanup(ctx.__exit__, None, None, None)


class TempLogMixin(SilentTestCase):
    """Give each test an ArchMaintenance whose log file lives in a temp dir."""

    def make(self, **kwargs):
        kwargs.setdefault('log_file', os.path.join(self.tmp.name, 'test.log'))
        return ArchMaintenance(**kwargs)

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)


class TestParseArgs(SilentTestCase):
    def test_defaults(self):
        args = parse_args([])
        self.assertEqual(args.keep, 3)
        self.assertFalse(args.noconfirm)
        self.assertFalse(args.dry_run)
        self.assertFalse(args.no_color)
        self.assertFalse(args.skip_system)
        self.assertFalse(args.skip_aur)
        self.assertFalse(args.skip_cache)
        self.assertFalse(args.skip_orphans)

    def test_keep_value(self):
        self.assertEqual(parse_args(['--keep', '5']).keep, 5)
        self.assertEqual(parse_args(['-k', '7']).keep, 7)

    def test_flags(self):
        args = parse_args(['-y', '-n', '--no-color'])
        self.assertTrue(args.noconfirm)
        self.assertTrue(args.dry_run)
        self.assertTrue(args.no_color)

    def test_skip_flags_independent(self):
        args = parse_args(['--skip-cache', '--skip-orphans'])
        self.assertTrue(args.skip_cache)
        self.assertTrue(args.skip_orphans)
        self.assertFalse(args.skip_system)
        self.assertFalse(args.skip_aur)


class TestColors(SilentTestCase):
    def setUp(self):
        super().setUp()
        # Colors mutates class attributes; restore originals after each test.
        saved = {name: getattr(Colors, name)
                 for name in ('BLUE', 'GREEN', 'YELLOW', 'RED', 'BOLD', 'END')}
        self.addCleanup(lambda: [setattr(Colors, k, v) for k, v in saved.items()])

    def test_disable_blanks_all_codes(self):
        Colors.disable()
        for name in ('BLUE', 'GREEN', 'YELLOW', 'RED', 'BOLD', 'END'):
            self.assertEqual(getattr(Colors, name), '')


class TestMaybeNoconfirm(TempLogMixin, unittest.TestCase):
    def test_appends_only_when_enabled(self):
        m = self.make(noconfirm=True)
        self.assertEqual(m.maybe_noconfirm(['pacman', '-Syu']),
                         ['pacman', '-Syu', '--noconfirm'])

    def test_leaves_command_untouched_by_default(self):
        m = self.make(noconfirm=False)
        self.assertEqual(m.maybe_noconfirm(['pacman', '-Syu']),
                         ['pacman', '-Syu'])


class TestCheckAurHelper(TempLogMixin, unittest.TestCase):
    def test_prefers_yay(self):
        m = self.make()
        with mock.patch('arch_maintain.shutil.which',
                        side_effect=lambda c: '/usr/bin/' + c):
            self.assertEqual(m.check_aur_helper(), 'yay')

    def test_falls_back_to_paru(self):
        m = self.make()
        which = lambda c: '/usr/bin/paru' if c == 'paru' else None
        with mock.patch('arch_maintain.shutil.which', side_effect=which):
            self.assertEqual(m.check_aur_helper(), 'paru')

    def test_none_when_no_helper(self):
        m = self.make()
        with mock.patch('arch_maintain.shutil.which', return_value=None):
            self.assertIsNone(m.check_aur_helper())


class TestRunCommand(TempLogMixin, unittest.TestCase):
    def test_success_records_completed(self):
        m = self.make()
        with mock.patch('arch_maintain.subprocess.run',
                        return_value=completed(0)) as run:
            self.assertTrue(m.run_command(['true'], 'ok'))
        run.assert_called_once()
        self.assertIn('ok', m.tasks_completed)
        self.assertEqual(m.tasks_failed, [])

    def test_failure_records_failed_with_exit_code(self):
        m = self.make()
        with mock.patch('arch_maintain.subprocess.run',
                        return_value=completed(1)):
            self.assertFalse(m.run_command(['false'], 'boom'))
        self.assertIn('boom', m.tasks_failed)
        self.assertEqual(m.tasks_completed, [])

    def test_missing_command(self):
        m = self.make()
        with mock.patch('arch_maintain.subprocess.run',
                        side_effect=FileNotFoundError):
            self.assertFalse(m.run_command(['nope'], 'missing'))
        self.assertIn('missing', m.tasks_failed)

    def test_dry_run_does_not_execute(self):
        m = self.make(dry_run=True)
        with mock.patch('arch_maintain.subprocess.run') as run:
            self.assertTrue(m.run_command(['pacman', '-Syu'], 'update'))
        run.assert_not_called()
        self.assertEqual(m.tasks_completed, ['update (dry-run)'])


class TestUpdateSystem(TempLogMixin, unittest.TestCase):
    def test_uses_aur_helper_alone_when_present(self):
        """The double-upgrade fix: with a helper we must NOT also run pacman."""
        m = self.make()
        with mock.patch.object(m, 'check_aur_helper', return_value='yay'), \
             mock.patch.object(m, 'run_command', return_value=True) as run:
            m.update_system()
        run.assert_called_once_with(['yay', '-Syu'], 'System + AUR update')

    def test_falls_back_to_pacman_without_helper(self):
        m = self.make()
        with mock.patch.object(m, 'check_aur_helper', return_value=None), \
             mock.patch.object(m, 'run_command', return_value=True) as run:
            m.update_system()
        run.assert_called_once_with(['sudo', 'pacman', '-Syu'], 'System update')

    def test_skip_aur_uses_pacman_even_with_helper(self):
        m = self.make(skip_aur=True)
        with mock.patch.object(m, 'check_aur_helper') as helper, \
             mock.patch.object(m, 'run_command', return_value=True) as run:
            m.update_system()
        helper.assert_not_called()
        run.assert_called_once_with(['sudo', 'pacman', '-Syu'], 'System update')

    def test_noconfirm_appended(self):
        m = self.make(noconfirm=True)
        with mock.patch.object(m, 'check_aur_helper', return_value='paru'), \
             mock.patch.object(m, 'run_command', return_value=True) as run:
            m.update_system()
        run.assert_called_once_with(['paru', '-Syu', '--noconfirm'],
                                    'System + AUR update')


class TestCleanCache(TempLogMixin, unittest.TestCase):
    def test_uses_paccache_with_keep(self):
        m = self.make(keep=5)
        with mock.patch('arch_maintain.shutil.which', return_value='/usr/bin/paccache'), \
             mock.patch.object(m, 'run_command', return_value=True) as run:
            m.clean_cache()
        run.assert_called_once_with(
            ['sudo', 'paccache', '-r', '-k5'], 'Cache cleaning')

    def test_falls_back_to_pacman_sc(self):
        m = self.make()
        with mock.patch('arch_maintain.shutil.which', return_value=None), \
             mock.patch.object(m, 'run_command', return_value=True) as run:
            m.clean_cache()
        run.assert_called_once_with(
            ['sudo', 'pacman', '-Sc'], 'Cache cleaning')


class TestRemoveOrphans(TempLogMixin, unittest.TestCase):
    def _qtdq(self, stdout, returncode=0):
        return SimpleNamespace(returncode=returncode, stdout=stdout, stderr='')

    def test_no_orphans(self):
        m = self.make()
        with mock.patch('arch_maintain.subprocess.run',
                        return_value=self._qtdq('')) as run, \
             mock.patch.object(m, 'run_command') as remove:
            self.assertTrue(m.remove_orphans())
        self.assertEqual(run.call_count, 1)  # single -Qtdq, nothing to remove
        remove.assert_not_called()
        self.assertIn('Remove orphans', m.tasks_completed)

    def test_single_pass(self):
        m = self.make()
        queries = [self._qtdq('pkg-a\npkg-b'), self._qtdq('')]
        with mock.patch('arch_maintain.subprocess.run', side_effect=queries), \
             mock.patch.object(m, 'run_command', return_value=True) as remove:
            self.assertTrue(m.remove_orphans())
        remove.assert_called_once_with(
            ['sudo', 'pacman', '-Rns', 'pkg-a', 'pkg-b'], 'Remove orphans')

    def test_multi_pass_until_clean(self):
        """Removing orphans can orphan their deps; the loop must repeat."""
        m = self.make()
        queries = [self._qtdq('pkg-a'), self._qtdq('pkg-b'), self._qtdq('')]
        with mock.patch('arch_maintain.subprocess.run', side_effect=queries), \
             mock.patch.object(m, 'run_command', return_value=True) as remove:
            self.assertTrue(m.remove_orphans())
        self.assertEqual(remove.call_count, 2)

    def test_stops_when_removal_fails(self):
        m = self.make()
        with mock.patch('arch_maintain.subprocess.run',
                        return_value=self._qtdq('pkg-a')), \
             mock.patch.object(m, 'run_command', return_value=False) as remove:
            self.assertFalse(m.remove_orphans())
        remove.assert_called_once()

    def test_dry_run_breaks_after_one_pass(self):
        """In dry-run nothing is removed, so guard against an infinite loop."""
        m = self.make(dry_run=True)
        with mock.patch('arch_maintain.subprocess.run',
                        return_value=self._qtdq('pkg-a')), \
             mock.patch.object(m, 'run_command', return_value=True) as remove:
            self.assertTrue(m.remove_orphans())
        remove.assert_called_once()


class TestPrimeSudo(TempLogMixin, unittest.TestCase):
    def test_success(self):
        m = self.make()
        with mock.patch('arch_maintain.subprocess.run',
                        return_value=completed(0)):
            self.assertTrue(m.prime_sudo())

    def test_failure(self):
        m = self.make()
        with mock.patch('arch_maintain.subprocess.run',
                        return_value=completed(1)):
            self.assertFalse(m.prime_sudo())

    def test_sudo_missing(self):
        m = self.make()
        with mock.patch('arch_maintain.subprocess.run',
                        side_effect=FileNotFoundError):
            self.assertFalse(m.prime_sudo())

    def test_dry_run_short_circuits(self):
        m = self.make(dry_run=True)
        with mock.patch('arch_maintain.subprocess.run') as run:
            self.assertTrue(m.prime_sudo())
        run.assert_not_called()


class TestRun(TempLogMixin, unittest.TestCase):
    def test_all_skipped(self):
        m = self.make(skip_system=True, skip_cache=True, skip_orphans=True)
        with mock.patch.object(m, 'prime_sudo', return_value=True), \
             mock.patch.object(m, 'update_system') as us, \
             mock.patch.object(m, 'clean_cache') as cc, \
             mock.patch.object(m, 'remove_orphans') as ro:
            m.run()
        us.assert_not_called()
        cc.assert_not_called()
        ro.assert_not_called()
        self.assertEqual(
            sorted(m.tasks_skipped),
            sorted(['System update', 'Cache cleaning', 'Remove orphans']))

    def test_aborts_when_sudo_unavailable(self):
        m = self.make()
        with mock.patch.object(m, 'prime_sudo', return_value=False), \
             mock.patch.object(m, 'update_system') as us:
            with self.assertRaises(SystemExit) as ctx:
                m.run()
        self.assertEqual(ctx.exception.code, 1)
        us.assert_not_called()

    def test_runs_enabled_tasks(self):
        m = self.make()
        with mock.patch.object(m, 'prime_sudo', return_value=True), \
             mock.patch.object(m, 'update_system') as us, \
             mock.patch.object(m, 'clean_cache') as cc, \
             mock.patch.object(m, 'remove_orphans') as ro:
            m.run()
        us.assert_called_once()
        cc.assert_called_once()
        ro.assert_called_once()


class TestMain(SilentTestCase):
    def test_refuses_to_run_as_root(self):
        with mock.patch('arch_maintain.os.geteuid', return_value=0), \
             mock.patch('sys.argv', ['arch_maintain.py']):
            with self.assertRaises(SystemExit) as ctx:
                arch_maintain.main()
        self.assertEqual(ctx.exception.code, 1)


if __name__ == '__main__':
    unittest.main()
