import sys


def _run_update_helper() -> int:
    from app.update.apply import run_update_helper
    # Retirer --update-helper des argv
    return run_update_helper(sys.argv[2:])


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--update-helper":
        raise SystemExit(_run_update_helper())

    from app.ui.main_window import launch
    launch()
