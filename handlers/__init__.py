import logging

from .start import register_start
from .help import register_help_command
from .buy import register_buy
from .combo import register_combo
from .redeem import register_redeem
from .me import register_me
from .single_commands import register_single_commands
from .admin_panel import register_admin_panel
from .fake import register_fake
from .gen import register_gen
from .bin_checker import register_bin_checker
def register_all(bot):
    logger = logging.getLogger("HANDLERS")

    handlers = [
        ("start", register_start),
        ("help", register_help_command),
        ("buy", register_buy),
        ("combo", register_combo),
        ("redeem", register_redeem),
        ("me", register_me),
        ("single_commands", register_single_commands),
        ("admin_panel", register_admin_panel),
        ("fake", register_fake),
        ("gen", register_gen),
        ("bin", register_bin_checker),
    ]

    for name, register_func in handlers:
        try:
            register_func(bot)
            logger.info(f"Handler registered: {name}")
        except Exception:
            logger.exception(f"Failed to register handler: {name}")