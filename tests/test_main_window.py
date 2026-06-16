"""Tests for MainWindow + MainWindowRenderer — preview frame and the renderer contract.

Verifies:
  - `_mirror_preview_frame` (now in `main_window_renderer`) does not mutate
    its input and produces a horizontally mirrored frame.
  - The renderer is the only consumer of cv2/numpy; main_window.py no
    longer imports those.
  - The renderer's `apply_plan` is the contract between the reducer
    logic and the widget tree; the renderer does not import
    classifier or types for branch logic.
"""

from __future__ import annotations

import numpy as np

from eyes.main_window_renderer import MainWindowRenderer, _mirror_preview_frame


class TestPreviewMirroring:
    def test_mirrors_frame_horizontally(self) -> None:
        frame = np.array(
            [
                [[10, 0, 0], [20, 0, 0], [30, 0, 0]],
                [[40, 0, 0], [50, 0, 0], [60, 0, 0]],
            ],
            dtype=np.uint8,
        )

        mirrored = _mirror_preview_frame(frame)

        expected = np.array(
            [
                [[30, 0, 0], [20, 0, 0], [10, 0, 0]],
                [[60, 0, 0], [50, 0, 0], [40, 0, 0]],
            ],
            dtype=np.uint8,
        )
        np.testing.assert_array_equal(mirrored, expected)

    def test_does_not_mutate_original_frame(self) -> None:
        frame = np.array(
            [[[1, 0, 0], [2, 0, 0]]],
            dtype=np.uint8,
        )
        original = frame.copy()

        _mirror_preview_frame(frame)

        np.testing.assert_array_equal(frame, original)


class TestMainWindowHasNoCv2OrNumpy:
    """main_window.py must not import cv2 or numpy directly."""

    def test_main_window_does_not_import_cv2(self) -> None:
        import eyes.main_window as module
        module_source = module.__file__
        assert module_source is not None
        with open(module_source, encoding="utf-8") as f:
            source = f.read()
        assert "import cv2" not in source
        assert "from cv2" not in source

    def test_main_window_does_not_import_numpy(self) -> None:
        import eyes.main_window as module
        module_source = module.__file__
        assert module_source is not None
        with open(module_source, encoding="utf-8") as f:
            source = f.read()
        assert "import numpy" not in source
        assert "from numpy" not in source


class TestRendererDoesNotImportClassifierOrTypes:
    """The renderer must not branch on PoseState or WarningLevel."""

    def test_renderer_does_not_import_classifier(self) -> None:
        from eyes import main_window_renderer as module
        module_source = module.__file__
        assert module_source is not None
        with open(module_source, encoding="utf-8") as f:
            source = f.read()
        assert "from .classifier" not in source
        assert "from eyes.classifier" not in source

    def test_renderer_does_not_import_types(self) -> None:
        from eyes import main_window_renderer as module
        module_source = module.__file__
        assert module_source is not None
        with open(module_source, encoding="utf-8") as f:
            source = f.read()
        assert "from .types" not in source
        assert "from eyes.types" not in source


class TestRendererImportsDisplayPlan:
    def test_renderer_imports_display_plan(self) -> None:
        from eyes import main_window_renderer as module
        module_source = module.__file__
        assert module_source is not None
        with open(module_source, encoding="utf-8") as f:
            source = f.read()
        assert "display_plan" in source


class TestMirrorPreviewFrameExported:
    """`_mirror_preview_frame` lives in the renderer module."""

    def test_helper_exists_in_renderer_module(self) -> None:
        from eyes.main_window_renderer import _mirror_preview_frame
        assert callable(_mirror_preview_frame)


# Mark MainWindowRenderer as used to keep the import.
_ = MainWindowRenderer
