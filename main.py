"""Eyes — entry point."""

import sys

from PySide6.QtWidgets import QApplication

from eyes.controller import AppController


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Eyes")

    camera_index = 0
    if len(sys.argv) > 1:
        try:
            camera_index = int(sys.argv[1])
        except ValueError:
            pass  # use default 0

    controller = AppController(app, camera_index=camera_index)
    controller.run()


if __name__ == "__main__":
    main()
