from typing import Optional

from config_wrangler.config_templates.config_hierarchy import ConfigHierarchy
from config_wrangler.config_templates.keepass_config import KeepassConfig
from config_wrangler.config_templates.password_source import PasswordSourceValidated


class PasswordDefaults(ConfigHierarchy):
    password_source: Optional[PasswordSourceValidated] = None

    keepass_config: str = 'keepass'
    """
    If the password_source is KEEPASS, then which root level config item contains
    the settings for Keepass (must be an instance of 
    :py:class:`config_wrangler.config_templates.keepass_config.KeepassConfig`)
    """
    keepass: Optional[KeepassConfig] = None
    """
    If the password_source is KEEPASS, then load a sub-section with the 
    :py:class:`config_wrangler.config_templates.keepass_config.KeepassConfig`) settings
    """
