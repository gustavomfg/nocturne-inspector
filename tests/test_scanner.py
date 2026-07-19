from __future__ import annotations

import unittest
from collections.abc import Callable, Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from nocturne_inspector.models import ProjectContext
from nocturne_inspector.scanner import ProjectScanner, scan_project


class ProjectContextTests(unittest.TestCase):
    def test_normalizes_inventory_languages_and_exclusions(self) -> None:
        context = ProjectContext(
            root=Path("/project"),
            files=(Path("z.py"), Path("a.py"), Path("z.py")),
            languages=("Python", "Python"),
            excluded_directories=("dist", "build", "dist"),
        )

        self.assertEqual(context.files, (Path("a.py"), Path("z.py")))
        self.assertEqual(context.languages, ("Python",))
        self.assertEqual(context.excluded_directories, ("build", "dist"))
        self.assertEqual(context.files_scanned, 2)

    def test_rejects_non_relative_inventory_paths(self) -> None:
        with self.assertRaises(ValueError):
            ProjectContext(root=Path("/project"), files=(Path("/outside.py"),))

        with self.assertRaises(ValueError):
            ProjectContext(root=Path("/project"), files=(Path("../outside.py"),))

        with self.assertRaises(ValueError):
            ProjectContext(
                root=Path("/project"),
                files=(),
                excluded_directories=("nested/cache",),
            )


class ProjectScannerTests(unittest.TestCase):
    def test_builds_ordered_inventory_and_detects_languages(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "src" / "z.ts").write_text("export {};\n", encoding="utf-8")
            (root / "src" / "a.py").write_text("pass\n", encoding="utf-8")
            (root / "notes.txt").write_text("notes\n", encoding="utf-8")

            context = scan_project(root)

            self.assertEqual(
                context.files,
                (Path("notes.txt"), Path("src/a.py"), Path("src/z.ts")),
            )
            self.assertEqual(context.languages, ("Python", "TypeScript"))
            self.assertEqual(context.files_scanned, 3)

    def test_excludes_named_directories_at_every_depth(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src" / "dist").mkdir(parents=True)
            (root / "src" / "dist" / "generated.py").touch()
            (root / "src" / "kept.py").touch()

            context = scan_project(root)

            self.assertEqual(context.files, (Path("src/kept.py"),))
            self.assertIn("dist", context.excluded_directories)

    def test_does_not_follow_file_or_directory_symlinks(self) -> None:
        with TemporaryDirectory() as directory, TemporaryDirectory() as external:
            root = Path(directory)
            external_root = Path(external)
            outside_file = external_root / "outside.py"
            outside_file.touch()
            (external_root / "package").mkdir()
            (external_root / "package" / "nested.py").touch()
            (root / "file-link.py").symlink_to(outside_file)
            (root / "directory-link").symlink_to(
                external_root / "package", target_is_directory=True
            )
            (root / "inside.py").touch()

            context = scan_project(root)

            self.assertEqual(context.files, (Path("inside.py"),))

    def test_propagates_permission_errors_instead_of_returning_partial_context(
        self,
    ) -> None:
        def fail_walk(
            path: Path,
            *,
            top_down: bool = True,
            on_error: Callable[[OSError], object] | None = None,
            follow_symlinks: bool = False,
        ) -> Iterator[tuple[Path, list[str], list[str]]]:
            del path, top_down, follow_symlinks
            if on_error is None:
                raise AssertionError("scanner must provide an error callback")
            on_error(PermissionError("denied"))
            return iter(())

        with (
            TemporaryDirectory() as directory,
            patch.object(Path, "walk", new=fail_walk),
        ):
            with self.assertRaisesRegex(PermissionError, "denied"):
                ProjectScanner().scan(Path(directory))

    def test_rejects_missing_and_non_directory_roots(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            project_file = root / "project.txt"
            project_file.touch()

            with self.assertRaises(FileNotFoundError):
                scan_project(root / "missing")

            with self.assertRaises(NotADirectoryError):
                scan_project(project_file)


if __name__ == "__main__":
    unittest.main()
