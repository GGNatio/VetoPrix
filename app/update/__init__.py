"""Package mise à jour à distance."""
from app.update.checker import check_for_update, start_update_and_quit

__all__ = ["check_for_update", "start_update_and_quit"]
